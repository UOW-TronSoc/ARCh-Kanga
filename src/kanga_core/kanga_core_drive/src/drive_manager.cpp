#include "kanga_core_drive/drive_manager.hpp"

#include <cctype>
#include <chrono>
#include <cstdlib>
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

bool DriveManager::wait_for_clients(
  const std::string & wheel_id,
  const WheelClients & wheel_clients)
{
  // Helper: confirm this wheel's clear_errors + request_axis_state exist.
  // Short wait — if custom_odrive_node is down, fail the request, don't hang.
  const std::string wheel_namespace = "/wheel_" + wheel_id;
  if (!wheel_clients.clear_errors_client->wait_for_service(2s)) {
    RCLCPP_ERROR(
      this->get_logger(), "Service not available: %s/clear_errors",
      wheel_namespace.c_str());
    return false;
  }
  if (!wheel_clients.axis_state_client->wait_for_service(2s)) {
    RCLCPP_ERROR(
      this->get_logger(), "Service not available: %s/request_axis_state",
      wheel_namespace.c_str());
    return false;
  }
  return true;
}

std_srvs::srv::Empty::Response::SharedPtr DriveManager::call_clear_errors(
  const rclcpp::Client<std_srvs::srv::Empty>::SharedPtr & client,
  const std_srvs::srv::Empty::Request::SharedPtr & request,
  std::chrono::seconds timeout)
{
  auto response_future = client->async_send_request(request);
  if (response_future.wait_for(timeout) != std::future_status::ready) {
    return nullptr;
  }
  return response_future.get();
}

custom_odrive::srv::AxisState::Response::SharedPtr DriveManager::call_axis_state(
  const rclcpp::Client<custom_odrive::srv::AxisState>::SharedPtr & client,
  const custom_odrive::srv::AxisState::Request::SharedPtr & request,
  std::chrono::seconds timeout)
{
  auto response_future = client->async_send_request(request);
  if (response_future.wait_for(timeout) != std::future_status::ready) {
    return nullptr;
  }
  return response_future.get();
}

bool DriveManager::request_idle_for_all_wheels()
{
  bool all_wheels_idle = true;
  for (const auto & wheel_id : wheel_ids_) {
    auto & wheel_clients = wheel_clients_by_id_.at(wheel_id);
    if (!wheel_clients.axis_state_client->wait_for_service(2s)) {
      RCLCPP_ERROR(
        this->get_logger(), "Cannot request IDLE; service missing for %s",
        wheel_id.c_str());
      all_wheels_idle = false;
      continue;
    }

    auto axis_state_request =
      std::make_shared<custom_odrive::srv::AxisState::Request>();
    axis_state_request->axis_requested_state = kAxisIdle;
    const auto axis_state_response = call_axis_state(
      wheel_clients.axis_state_client, axis_state_request, 15s);
    if (!axis_state_response || !axis_state_response->success) {
      RCLCPP_ERROR(
        this->get_logger(), "IDLE request failed for %s", wheel_id.c_str());
      all_wheels_idle = false;
    }
  }
  return all_wheels_idle;
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

  std::ostringstream result_messages;

  // Fail the whole request if any wheel cannot transition, then request IDLE
  // for all wheels so a partial CLOSED_LOOP sequence cannot remain armed.
  for (const auto & wheel_id : wheel_ids_) {
    auto & wheel_clients = wheel_clients_by_id_.at(wheel_id);
    if (!wait_for_clients(wheel_id, wheel_clients)) {
      report_closed_loop_failure(
        response, "services missing for " + wheel_id);
      return;
    }

    // Clear sticky faults before CLOSED_LOOP so a prior trip does not
    // immediately bounce the axis back out.
    auto clear_errors_request =
      std::make_shared<std_srvs::srv::Empty::Request>();
    const auto clear_errors_response = call_clear_errors(
      wheel_clients.clear_errors_client, clear_errors_request, 5s);
    if (!clear_errors_response) {
      report_closed_loop_failure(
        response, "clear_errors timed out for " + wheel_id);
      return;
    }

    auto axis_state_request =
      std::make_shared<custom_odrive::srv::AxisState::Request>();
    axis_state_request->axis_requested_state = kAxisClosedLoop;
    const auto axis_state_response = call_axis_state(
      wheel_clients.axis_state_client, axis_state_request, 15s);
    if (!axis_state_response || !axis_state_response->success) {
      report_closed_loop_failure(
        response, "CLOSED_LOOP failed for " + wheel_id);
      return;
    }
    if (!result_messages.str().empty()) {
      result_messages << ", ";
    }
    result_messages << wheel_id << ":closed_loop";
  }

  response->success = true;
  response->message = result_messages.str();
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
