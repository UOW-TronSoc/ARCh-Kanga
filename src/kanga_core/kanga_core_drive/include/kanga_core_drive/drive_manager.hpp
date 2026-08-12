#pragma once

/*
 * DriveManager — drive state, all-wheel error clearing, and calibration.
 *
 * Owns ROS services only; does not stream setpoints (that is kanga_core_controller)
 * and does not talk Fibre/CAN itself (commission_wheels → custom_odrive commission).
 *
 * Services this node offers (names relative to the node, e.g. /drive_manager/…):
 *
 *   ~/set_closed_loop  (std_srvs/SetBool)
 *     Put every wheel into CLOSED_LOOP or IDLE via custom_odrive request_axis_state.
 *     data=true  → clear_errors, then CLOSED_LOOP (state 8) on each wheel
 *     data=false → IDLE (state 1) on each wheel
 *     Does NOT call set_enabled / start_enabled — use /drivestop for global stop.
 *
 *   ~/clear_errors  (std_srvs/Trigger)
 *     Clear sticky errors on every wheel without changing requested axis state.
 *
 *   ~/calibrate_fl, ~/calibrate_bl, ~/calibrate_br, ~/calibrate_fr  (std_srvs/Trigger)
 *     Run Fibre FULL_CALIBRATION on that one wheel.
 *     Shells: ros2 run kanga_core_drive commission_wheels -- --wheels <id> --calibrate
 *
 * All handlers share drive_operation_mutex_ (try_lock): a second call while one is running
 * fails immediately with message "busy" instead of queueing long work.
 */

#include <memory>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

#include "custom_odrive/srv/axis_state.hpp"
#include "rclcpp/rclcpp.hpp"
#include "std_srvs/srv/empty.hpp"
#include "std_srvs/srv/set_bool.hpp"
#include "std_srvs/srv/trigger.hpp"

class DriveManager : public rclcpp::Node
{
public:
  // Declares params, creates per-wheel clients, advertises services.
  explicit DriveManager(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());

private:
  // ODrive Axis.requested_state values (see ODrive docs / custom_odrive).
  static constexpr uint32_t kAxisIdle = 1;
  static constexpr uint32_t kAxisClosedLoop = 8;

  // Clients we call on each /wheel_<id>/ custom_odrive_node.
  struct WheelClients
  {
    rclcpp::Client<std_srvs::srv::Empty>::SharedPtr clear_errors_client;
    rclcpp::Client<custom_odrive::srv::AxisState>::SharedPtr axis_state_client;
  };

  // Send clear-errors requests to every wheel together and return any failures.
  std::vector<std::string> clear_errors_for_all_wheels();

  // Send one requested axis state to every wheel together and return failures.
  std::vector<std::string> request_axis_state_for_all_wheels(
    uint32_t requested_state);

  // Attempt to leave every wheel safe in IDLE, even if an earlier one fails.
  bool request_idle_for_all_wheels();

  // Report a failed CLOSED_LOOP transition after attempting an IDLE rollback.
  void report_closed_loop_failure(
    const std::shared_ptr<std_srvs::srv::SetBool::Response> & response,
    const std::string & reason);

  // Handler for ~/set_closed_loop — see class comment above.
  void handle_set_closed_loop(
    const std::shared_ptr<std_srvs::srv::SetBool::Request> request,
    std::shared_ptr<std_srvs::srv::SetBool::Response> response);

  // Handler for ~/clear_errors — attempt every wheel even if one call fails.
  void handle_clear_errors(
    const std::shared_ptr<std_srvs::srv::Trigger::Request> request,
    std::shared_ptr<std_srvs::srv::Trigger::Response> response);

  // Shared body for ~/calibrate_<id> Trigger services.
  void handle_calibrate(
    const std::string & wheel_id,
    const std::shared_ptr<std_srvs::srv::Trigger::Request> request,
    std::shared_ptr<std_srvs::srv::Trigger::Response> response);

  std::vector<std::string> wheel_ids_;
  std::string can_interface_;    // forwarded to commission_wheels --can
  std::string drivetrain_profile_;    // forwarded to commission_wheels
  std::mutex drive_operation_mutex_;
  // Callback group that allows overlapping callbacks (ROS type name:
  // CallbackGroupType::Reentrant). Needed because handlers wait for service
  // responses or std::system; without it the executor can deadlock waiting
  // for a reply that never gets spun. Pair with MultiThreadedExecutor in main.
  rclcpp::CallbackGroup::SharedPtr service_callback_group_;
  std::unordered_map<std::string, WheelClients> wheel_clients_by_id_;
  rclcpp::Service<std_srvs::srv::SetBool>::SharedPtr set_closed_loop_service_;
  rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr clear_errors_service_;
  std::vector<rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr>
  calibration_services_;
};
