#include "kanga_core_drive/drive_manager.hpp"

#include <cctype>
#include <chrono>
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

}  // namespace

DriveManager::DriveManager(const rclcpp::NodeOptions & options)
: Node("drive_manager", options)
{
  // wheel_ids / can_interface come from launch (drive.launch.py).
  // can_interface is forwarded into calibrate_* → commission_wheels.
  this->declare_parameter<std::vector<std::string>>(
    "wheel_ids", {"fl", "bl", "br", "fr"});
  this->declare_parameter<std::string>("can_interface", "can_core");
  this->declare_parameter<std::string>("drivetrain_profile");

  wheel_ids_ = this->get_parameter("wheel_ids").as_string_array();
  can_interface_ = this->get_parameter("can_interface").as_string();
  drivetrain_profile_ = this->get_parameter("drivetrain_profile").as_string();
  for (auto & wheel_id : wheel_ids_) {
    wheel_id = to_lower(wheel_id);
  }

  // Allow overlapping callbacks in this group (ROS calls this "Reentrant").
  // Handlers block waiting on wheel services / shelling commission; if the
  // group were mutually exclusive, the reply callback could never run and
  // we'd deadlock. MultiThreadedExecutor in main spins the other work.
  service_callback_group_ =
    this->create_callback_group(rclcpp::CallbackGroupType::Reentrant);

  // One client pair per wheel under /wheel_<id>/… (custom_odrive_node services).
  // Intentionally no set_enabled clients — stop is /drivestop, not latching enable.
  for (const auto & wheel_id : wheel_ids_) {
    const std::string wheel_namespace = "/wheel_" + wheel_id;
    WheelClients wheel_clients;
    // /wheel_<id>/clear_errors — clear ODrive sticky faults before CLOSED_LOOP.
    wheel_clients.clear_errors_client =
      this->create_client<std_srvs::srv::Empty>(
      wheel_namespace + "/clear_errors", rmw_qos_profile_services_default,
      service_callback_group_);
    // /wheel_<id>/request_axis_state — set IDLE (1) or CLOSED_LOOP (8).
    wheel_clients.axis_state_client =
      this->create_client<custom_odrive::srv::AxisState>(
      wheel_namespace + "/request_axis_state", rmw_qos_profile_services_default,
      service_callback_group_);
    wheel_clients_by_id_[wheel_id] = wheel_clients;
  }

  // Service: CLOSED_LOOP all wheels (true) or IDLE all wheels (false). See header.
  set_closed_loop_service_ = this->create_service<std_srvs::srv::SetBool>(
    "~/set_closed_loop",
    std::bind(
      &DriveManager::handle_set_closed_loop, this, std::placeholders::_1,
      std::placeholders::_2),
    rmw_qos_profile_services_default, service_callback_group_);

  // Service: clear sticky errors on every wheel without changing axis state.
  clear_errors_service_ = this->create_service<std_srvs::srv::Trigger>(
    "~/clear_errors",
    std::bind(
      &DriveManager::handle_clear_errors, this, std::placeholders::_1,
      std::placeholders::_2),
    rmw_qos_profile_services_default, service_callback_group_);

  // One Trigger per wheel — basestation can bind one button → one service.
  for (const auto & wheel_id : wheel_ids_) {
    const std::string service_name = "~/calibrate_" + wheel_id;
    calibration_services_.push_back(
      this->create_service<std_srvs::srv::Trigger>(
        service_name,
        std::bind(
          &DriveManager::handle_calibrate, this, wheel_id,
          std::placeholders::_1, std::placeholders::_2),
        rmw_qos_profile_services_default, service_callback_group_));
  }

  RCLCPP_INFO(this->get_logger(), "drive_manager ready (%zu wheels)", wheel_ids_.size());
}

std::vector<std::string> DriveManager::clear_errors_for_all_wheels()
{
  using ClearErrorsFuture =
    rclcpp::Client<std_srvs::srv::Empty>::SharedFuture;
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
      wheel_id, client->async_send_request(request).share());
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

std::vector<std::string> DriveManager::request_axis_state_for_all_wheels(
  uint32_t requested_state)
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
    auto request =
      std::make_shared<custom_odrive::srv::AxisState::Request>();
    request->axis_requested_state = requested_state;
    pending_requests.emplace_back(
      wheel_id, client->async_send_request(request).share());
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
  response->message = reason +
    (rollback_succeeded ? "; all wheels returned to IDLE" :
    "; IDLE rollback incomplete");
}

void DriveManager::handle_set_closed_loop(
  const std::shared_ptr<std_srvs::srv::SetBool::Request> request,
  std::shared_ptr<std_srvs::srv::SetBool::Response> response)
{
  // ~/set_closed_loop handler: true → CLOSED_LOOP all wheels; false → IDLE all.
  // try_lock: refuse overlapping CLOSED_LOOP/calibrate rather than queue long work.
  std::unique_lock<std::mutex> operation_lock(
    drive_operation_mutex_, std::try_to_lock);
  if (!operation_lock.owns_lock()) {
    response->success = false;
    response->message = "busy";
    return;
  }

  if (!request->data) {
    response->success = request_idle_for_all_wheels();
    response->message = response->success ?
      "all wheels idle" : "one or more wheels failed to enter IDLE";
    return;
  }

  // Clear all wheels together before requesting CLOSED_LOOP together.
  const auto clear_errors_failures = clear_errors_for_all_wheels();
  if (!clear_errors_failures.empty()) {
    report_closed_loop_failure(
      response, "clear_errors failed: " +
      join_messages(clear_errors_failures));
    return;
  }

  const auto closed_loop_failures =
    request_axis_state_for_all_wheels(kAxisClosedLoop);
  if (!closed_loop_failures.empty()) {
    report_closed_loop_failure(
      response, "CLOSED_LOOP failed: " +
      join_messages(closed_loop_failures));
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
  std::unique_lock<std::mutex> operation_lock(
    drive_operation_mutex_, std::try_to_lock);
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

void DriveManager::handle_calibrate(
  const std::string & wheel_id,
  const std::shared_ptr<std_srvs::srv::Trigger::Request>/*request*/,
  std::shared_ptr<std_srvs::srv::Trigger::Response> response)
{
  // ~/calibrate_<id> handler: one-wheel FULL_CALIBRATION via commission_wheels.
  // Basestation motor-status page: one button → one Trigger service.
  std::unique_lock<std::mutex> operation_lock(
    drive_operation_mutex_, std::try_to_lock);
  if (!operation_lock.owns_lock()) {
    response->success = false;
    response->message = "busy";
    return;
  }

  // Shell out to the Python commission wrapper (Fibre apply + FULL_CALIBRATION).
  // Interactive prompts inside custom_odrive commission still apply on the TTY.
  std::ostringstream commission_command;
  commission_command
    << "ros2 run kanga_core_drive commission_wheels -- --wheels " << wheel_id
    << " --can " << shell_quote(can_interface_)
    << " --drivetrain-profile " << shell_quote(drivetrain_profile_)
    << " --calibrate";
  RCLCPP_INFO(
    this->get_logger(), "Calibrating %s: %s", wheel_id.c_str(),
    commission_command.str().c_str());
  const int system_status = std::system(commission_command.str().c_str());
  if (system_status == -1) {
    response->success = false;
    response->message = "failed to start commission_wheels";
    return;
  }
  if (!WIFEXITED(system_status)) {
    response->success = false;
    response->message = "commission_wheels terminated abnormally";
    return;
  }
  const int commission_exit_code = WEXITSTATUS(system_status);
  if (commission_exit_code != 0) {
    response->success = false;
    response->message =
      "commission_wheels exited " + std::to_string(commission_exit_code);
    return;
  }
  response->success = true;
  response->message = "calibrated " + wheel_id;
}
