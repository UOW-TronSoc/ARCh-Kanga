#include "kanga_core_drive/drive_manager.hpp"

#include <array>
#include <cctype>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <future>
#include <sstream>
#include <sys/wait.h>

using namespace std::chrono_literals;

namespace
{

// Normalise wheel ids from params (FL → fl).
std::string to_lower(std::string value)
{
  for (char & ch : value) {
    ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
  }
  return value;
}

// Quote a launch-provided value for the commissioning shell command.
std::string shell_quote(const std::string & value)
{
  std::string out{"'"};
  for (const char ch : value) {
    if (ch == '\'') {
      out += "'\\''";
    } else {
      out += ch;
    }
  }
  out += '\'';
  return out;
}

// Join per-wheel failures into one service response message.
std::string join_messages(const std::vector<std::string> & messages)
{
  std::ostringstream joined;
  for (const auto & message : messages) {
    if (!joined.str().empty()) {
      joined << ", ";
    }
    joined << message;
  }
  return joined.str();
}

struct CommandResult
{
  bool started{false};
  bool exited_normally{false};
  int exit_code{-1};
  std::string output;
};

// Run a commissioning command while retaining its combined stdout/stderr.
// std::system() exposed only an exit code, which left the browser reporting
// "commission_wheels exited 1" and discarded the useful Python/Fibre error.
CommandResult run_command_with_output(const std::string & command)
{
  CommandResult result;
  FILE * pipe = popen((command + " 2>&1").c_str(), "r");
  if (pipe == nullptr) {
    return result;
  }
  result.started = true;

  std::array<char, 512> buffer{};
  while (fgets(buffer.data(), static_cast<int>(buffer.size()), pipe) !=
    nullptr)
  {
    result.output += buffer.data();
    // Commissioning output is normally short. Retain the final 16 KiB if a
    // dependency becomes noisy so one request cannot grow memory indefinitely.
    constexpr std::size_t max_output_bytes = 16U * 1024U;
    if (result.output.size() > max_output_bytes) {
      result.output.erase(0, result.output.size() - max_output_bytes);
    }
  }

  const int status = pclose(pipe);
  if (status != -1 && WIFEXITED(status)) {
    result.exited_normally = true;
    result.exit_code = WEXITSTATUS(status);
  }
  return result;
}

std::string trim(std::string value)
{
  while (!value.empty() &&
    std::isspace(static_cast<unsigned char>(value.front())))
  {
    value.erase(value.begin());
  }
  while (!value.empty() &&
    std::isspace(static_cast<unsigned char>(value.back())))
  {
    value.pop_back();
  }
  return value;
}

// Keep the complete transcript in the ROS log, but return only its most useful
// failure line to the commissioning page. Markers are ordered from the most
// specific hardware/procedure failures to broader setup failures.
std::string concise_failure_detail(const std::string & output)
{
  std::vector<std::string> lines;
  std::istringstream stream(output);
  std::string line;
  while (std::getline(stream, line)) {
    line = trim(line);
    if (!line.empty()) {
      lines.push_back(line);
    }
  }

  const std::array<const char *, 12> useful_markers = {
    "calibration failed:",
    "calibration timed out",
    "calibration ended with",
    "save_configuration failed:",
    "failed to find ODrive",
    "no ODrive with serial",
    "services not available under",
    "set_enabled(false) failed",
    "request_axis_state(IDLE) failed",
    "/drivestop is asserted",
    "Missing shared config",
    "Missing wheel config",
  };
  for (const char * marker : useful_markers) {
    for (const std::string & candidate : lines) {
      const std::size_t marker_position = candidate.find(marker);
      if (marker_position != std::string::npos) {
        // Interactive prompts do not necessarily end with a newline. Return
        // from the useful marker so a preceding safety prompt cannot become
        // part of the compact browser error.
        return candidate.substr(marker_position);
      }
    }
  }

  // Unknown failures should still be useful without returning command echoes
  // and ros2-runner boilerplate. Walk backward because exception summaries are
  // conventionally printed at the end.
  for (auto candidate = lines.rbegin(); candidate != lines.rend(); ++candidate) {
    if (candidate->rfind("[ros2run]", 0) == 0 ||
      candidate->rfind("Commission failed", 0) == 0 ||
      candidate->front() == '+')
    {
      continue;
    }
    constexpr std::size_t max_message_bytes = 600U;
    if (candidate->size() > max_message_bytes) {
      return "..." + candidate->substr(candidate->size() - max_message_bytes);
    }
    return *candidate;
  }
  return "";
}

} // namespace

DriveManager::DriveManager(const rclcpp::NodeOptions & options)
: Node("drive_manager", options)
{
  // wheel_ids / can_interface come from launch (drive.launch.py).
  // can_interface is forwarded into calibrate_* → commission_wheels.
  this->declare_parameter<std::vector<std::string>>(
    "wheel_ids",
    {"fl", "bl", "br", "fr"});
  this->declare_parameter<std::string>("can_interface", "can_core");
  this->declare_parameter<std::string>("drivetrain_profile");
  this->declare_parameter<std::string>("motor_limits");

  wheel_ids_ = this->get_parameter("wheel_ids").as_string_array();
  can_interface_ = this->get_parameter("can_interface").as_string();
  drivetrain_profile_ = this->get_parameter("drivetrain_profile").as_string();
  motor_limits_ = this->get_parameter("motor_limits").as_string();
  for (auto & wheel_id : wheel_ids_) {
    wheel_id = to_lower(wheel_id);
  }

  // Allow overlapping callbacks in this group (ROS calls this "Reentrant").
  // Handlers block waiting on wheel services / shelling commission; if the
  // group were mutually exclusive, the reply callback could never run and
  // we'd deadlock. MultiThreadedExecutor in main spins the other work.
  service_callback_group_ =
    this->create_callback_group(rclcpp::CallbackGroupType::Reentrant);

  // One client group per wheel under /wheel_<id>/… (custom_odrive_node
  // services). set_enabled is not a second operator stop here: commissioning
  // uses it to park a node, and CLOSED_LOOP restores that local latch.
  for (const auto & wheel_id : wheel_ids_) {
    const std::string wheel_namespace = "/wheel_" + wheel_id;
    WheelClients wheel_clients;
    // /wheel_<id>/set_enabled — re-arm the node after commissioning parked it.
    wheel_clients.enabled_client =
      this->create_client<std_srvs::srv::SetBool>(
      wheel_namespace + "/set_enabled", rmw_qos_profile_services_default,
      service_callback_group_);
    // /wheel_<id>/clear_errors — clear ODrive sticky faults before CLOSED_LOOP.
    wheel_clients.clear_errors_client =
      this->create_client<std_srvs::srv::Empty>(
      wheel_namespace + "/clear_errors", rmw_qos_profile_services_default,
      service_callback_group_);
    // /wheel_<id>/request_axis_state — set IDLE (1) or CLOSED_LOOP (8).
    wheel_clients.axis_state_client =
      this->create_client<custom_odrive::srv::AxisState>(
      wheel_namespace + "/request_axis_state",
      rmw_qos_profile_services_default, service_callback_group_);
    wheel_clients_by_id_[wheel_id] = wheel_clients;
  }

  // Service: CLOSED_LOOP all wheels (true) or IDLE all wheels (false). See
  // header.
  set_closed_loop_service_ = this->create_service<std_srvs::srv::SetBool>(
    "~/set_closed_loop",
    std::bind(
      &DriveManager::handle_set_closed_loop, this,
      std::placeholders::_1, std::placeholders::_2),
    rmw_qos_profile_services_default, service_callback_group_);

  // Service: clear sticky errors on every wheel without changing axis state.
  clear_errors_service_ = this->create_service<std_srvs::srv::Trigger>(
    "~/clear_errors",
    std::bind(
      &DriveManager::handle_clear_errors, this, std::placeholders::_1,
      std::placeholders::_2),
    rmw_qos_profile_services_default, service_callback_group_);

  // One save Trigger and one calibration Trigger per wheel. A calibration
  // service call is itself the caller's off-ground acknowledgement; the
  // browser API will only call it after its confirmation popup is accepted.
  for (const auto & wheel_id : wheel_ids_) {
    const std::string save_service_name = "~/save_" + wheel_id;
    save_services_.push_back(
      this->create_service<std_srvs::srv::Trigger>(
        save_service_name,
        std::bind(
          &DriveManager::handle_commission, this, wheel_id, false,
          std::placeholders::_1, std::placeholders::_2),
        rmw_qos_profile_services_default, service_callback_group_));

    const std::string calibration_service_name = "~/calibrate_" + wheel_id;
    calibration_services_.push_back(
      this->create_service<std_srvs::srv::Trigger>(
        calibration_service_name,
        std::bind(
          &DriveManager::handle_commission, this, wheel_id, true,
          std::placeholders::_1, std::placeholders::_2),
        rmw_qos_profile_services_default, service_callback_group_));
  }

  RCLCPP_INFO(
    this->get_logger(), "drive_manager ready (%zu wheels)",
    wheel_ids_.size());
}

std::vector<std::string> DriveManager::enable_all_wheels()
{
  using SetEnabledFuture =
    rclcpp::Client<std_srvs::srv::SetBool>::SharedFuture;
  std::vector<std::pair<std::string, SetEnabledFuture>> pending_requests;
  std::vector<std::string> failures;

  // Dispatch every available request before waiting, so all wheels share one
  // response window instead of being re-enabled serially.
  for (const auto & wheel_id : wheel_ids_) {
    auto & client = wheel_clients_by_id_.at(wheel_id).enabled_client;
    if (!client->wait_for_service(2s)) {
      failures.push_back(wheel_id + ":service unavailable");
      continue;
    }
    auto request = std::make_shared<std_srvs::srv::SetBool::Request>();
    request->data = true;
    pending_requests.emplace_back(
      wheel_id,
      client->async_send_request(request).share());
  }

  const auto deadline = std::chrono::steady_clock::now() + 5s;
  for (auto & pending_request : pending_requests) {
    if (pending_request.second.wait_until(deadline) !=
      std::future_status::ready)
    {
      failures.push_back(pending_request.first + ":timeout");
      continue;
    }

    const auto response = pending_request.second.get();
    if (!response->success) {
      const std::string detail = response->message.empty() ?
        "request failed" : response->message;
      failures.push_back(pending_request.first + ":" + detail);
    }
  }
  return failures;
}

std::vector<std::string> DriveManager::clear_errors_for_all_wheels()
{
  using ClearErrorsFuture = rclcpp::Client<std_srvs::srv::Empty>::SharedFuture;
  std::vector<std::pair<std::string, ClearErrorsFuture>> pending_requests;
  std::vector<std::string> failures;

  // Dispatch every available request before waiting for any response.
  for (const auto & wheel_id : wheel_ids_) {
    auto & client = wheel_clients_by_id_.at(wheel_id).clear_errors_client;
    if (!client->wait_for_service(2s)) {
      failures.push_back(wheel_id + ":service unavailable");
      continue;
    }
    auto request = std::make_shared<std_srvs::srv::Empty::Request>();
    pending_requests.emplace_back(
      wheel_id,
      client->async_send_request(request).share());
  }

  // All requests share one five-second response window.
  const auto deadline = std::chrono::steady_clock::now() + 5s;
  for (auto & pending_request : pending_requests) {
    if (pending_request.second.wait_until(deadline) !=
      std::future_status::ready)
    {
      failures.push_back(pending_request.first + ":timeout");
    }
  }
  return failures;
}

std::vector<std::string>
DriveManager::request_axis_state_for_all_wheels(uint32_t requested_state)
{
  using AxisStateFuture =
    rclcpp::Client<custom_odrive::srv::AxisState>::SharedFuture;
  std::vector<std::pair<std::string, AxisStateFuture>> pending_requests;
  std::vector<std::string> failures;

  // Dispatch every available request before waiting for any response.
  for (const auto & wheel_id : wheel_ids_) {
    auto & client = wheel_clients_by_id_.at(wheel_id).axis_state_client;
    if (!client->wait_for_service(2s)) {
      failures.push_back(wheel_id + ":service unavailable");
      continue;
    }
    auto request = std::make_shared<custom_odrive::srv::AxisState::Request>();
    request->axis_requested_state = requested_state;
    pending_requests.emplace_back(
      wheel_id,
      client->async_send_request(request).share());
  }

  // All requests share one 15-second response window.
  const auto deadline = std::chrono::steady_clock::now() + 15s;
  for (auto & pending_request : pending_requests) {
    if (pending_request.second.wait_until(deadline) !=
      std::future_status::ready)
    {
      failures.push_back(pending_request.first + ":timeout");
      continue;
    }
    if (!pending_request.second.get()->success) {
      failures.push_back(pending_request.first + ":request failed");
    }
  }
  return failures;
}

bool DriveManager::request_idle_for_all_wheels()
{
  const auto failures = request_axis_state_for_all_wheels(kAxisIdle);
  if (!failures.empty()) {
    RCLCPP_ERROR(
      this->get_logger(), "IDLE failures: %s",
      join_messages(failures).c_str());
  }
  return failures.empty();
}

void DriveManager::report_closed_loop_failure(
  const std::shared_ptr<std_srvs::srv::SetBool::Response> & response,
  const std::string & reason)
{
  const bool rollback_succeeded = request_idle_for_all_wheels();
  response->success = false;
  response->message =
    reason + (rollback_succeeded ? "; all wheels returned to IDLE" :
    "; IDLE rollback incomplete");
}

void DriveManager::handle_set_closed_loop(
  const std::shared_ptr<std_srvs::srv::SetBool::Request> request,
  std::shared_ptr<std_srvs::srv::SetBool::Response> response)
{
  // ~/set_closed_loop handler: true → CLOSED_LOOP all wheels; false → IDLE all.
  // try_lock: refuse overlapping CLOSED_LOOP/calibrate rather than queue long
  // work.
  std::unique_lock<std::mutex> operation_lock(drive_operation_mutex_,
    std::try_to_lock);
  if (!operation_lock.owns_lock()) {
    response->success = false;
    response->message = "busy";
    return;
  }

  if (!request->data) {
    response->success = request_idle_for_all_wheels();
    response->message = response->success ?
      "all wheels idle" :
      "one or more wheels failed to enter IDLE";
    return;
  }

  // Commissioning parks custom_odrive_node with set_enabled(false) to prevent
  // CAN command races while Fibre owns the motor. The operator's explicit
  // CLOSED_LOOP request is the correct point to restore those local latches.
  const auto enable_failures = enable_all_wheels();
  if (!enable_failures.empty()) {
    report_closed_loop_failure(
      response,
      "set_enabled(true) failed: " + join_messages(enable_failures));
    return;
  }

  // Clear all wheels together before requesting CLOSED_LOOP together.
  const auto clear_errors_failures = clear_errors_for_all_wheels();
  if (!clear_errors_failures.empty()) {
    report_closed_loop_failure(
      response,
      "clear_errors failed: " +
      join_messages(clear_errors_failures));
    return;
  }

  const auto closed_loop_failures =
    request_axis_state_for_all_wheels(kAxisClosedLoop);
  if (!closed_loop_failures.empty()) {
    report_closed_loop_failure(
      response, "CLOSED_LOOP failed: " + join_messages(closed_loop_failures));
    return;
  }

  std::ostringstream result_messages;
  for (const auto & wheel_id : wheel_ids_) {
    if (!result_messages.str().empty()) {
      result_messages << ", ";
    }
    result_messages << wheel_id << ":closed_loop";
  }
  response->success = true;
  response->message = result_messages.str();
}

void DriveManager::handle_clear_errors(
  const std::shared_ptr<std_srvs::srv::Trigger::Request>/*request*/,
  std::shared_ptr<std_srvs::srv::Trigger::Response> response)
{
  // Refuse overlapping state, calibration, or error-clearing operations.
  std::unique_lock<std::mutex> operation_lock(drive_operation_mutex_,
    std::try_to_lock);
  if (!operation_lock.owns_lock()) {
    response->success = false;
    response->message = "busy";
    return;
  }

  const auto failures = clear_errors_for_all_wheels();
  response->success = failures.empty();
  response->message = response->success ?
    "cleared errors on all wheels" :
    "clear_errors failed: " + join_messages(failures);
}

void DriveManager::handle_commission(
  const std::string & wheel_id, bool calibrate,
  const std::shared_ptr<std_srvs::srv::Trigger::Request>/*request*/,
  std::shared_ptr<std_srvs::srv::Trigger::Response> response)
{
  // Both operations apply the active shared/individual/limit config and save
  // it to NVRAM. Calibration additionally runs FULL_CALIBRATION_SEQUENCE.
  std::unique_lock<std::mutex> operation_lock(drive_operation_mutex_,
    std::try_to_lock);
  if (!operation_lock.owns_lock()) {
    response->success = false;
    response->message = "busy";
    return;
  }

  // Stop the whole drivetrain before touching one ODrive. The Fibre helper
  // then disables the selected motor's ROS latch and leaves it disabled.
  if (!request_idle_for_all_wheels()) {
    response->success = false;
    response->message = "could not put every wheel in IDLE; commission aborted";
    return;
  }

  // Always pass the ROS namespace (commission_wheels does that unless --bench
  // is explicitly requested). This makes an unavailable motor node an error
  // instead of asking a browser user to answer a bench-mode question.
  std::ostringstream commission_command;
  commission_command
    << "ros2 run kanga_core_drive commission_wheels -- --wheels " << wheel_id
    << " --can " << shell_quote(can_interface_) << " --drivetrain-profile "
    << shell_quote(drivetrain_profile_) << " --motor-limits "
    << shell_quote(motor_limits_);
  if (calibrate) {
    // Reaching this internal service means the higher-level caller collected
    // a fresh off-ground confirmation for this exact motor.
    commission_command << " --calibrate --off-ground-confirmed";
  }
  commission_command << " --save";

  const std::string operation = calibrate ? "Calibrating and saving" : "Saving";
  RCLCPP_INFO(
    this->get_logger(), "%s %s: %s", operation.c_str(),
    wheel_id.c_str(), commission_command.str().c_str());
  const CommandResult command_result =
    run_command_with_output(commission_command.str());
  if (!command_result.output.empty()) {
    RCLCPP_INFO(
      this->get_logger(), "commission_wheels output for %s:\n%s",
      wheel_id.c_str(), command_result.output.c_str());
  }
  if (!command_result.started) {
    response->success = false;
    response->message = "failed to start commission_wheels";
    return;
  }
  if (!command_result.exited_normally) {
    response->success = false;
    response->message = "commission_wheels terminated abnormally";
    return;
  }
  if (command_result.exit_code != 0) {
    response->success = false;
    const std::string detail = concise_failure_detail(command_result.output);
    response->message = detail.empty() ?
      "commission_wheels exited " +
      std::to_string(command_result.exit_code) :
      detail;
    return;
  }
  response->success = true;
  response->message = calibrate ? "calibrated and saved " + wheel_id :
    "applied and saved " + wheel_id;
}
