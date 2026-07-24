#pragma once

/*
 * DriveManager — CLOSED_LOOP / IDLE requests and single-wheel calibration.
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
 *   ~/calibrate_fl, ~/calibrate_bl, ~/calibrate_br, ~/calibrate_fr  (std_srvs/Trigger)
 *     Run Fibre FULL_CALIBRATION on that one wheel.
 *     Shells: ros2 run kanga_core_drive commission_wheels -- --wheels <id> --calibrate
 *
 * All handlers share busy_mutex_ (try_lock): a second call while one is running
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
        rclcpp::Client<std_srvs::srv::Empty>::SharedPtr clear_errors;  // wipe sticky faults
        rclcpp::Client<custom_odrive::srv::AxisState>::SharedPtr axis_state;  // IDLE / CLOSED_LOOP
    };

    // Return true if both services for this wheel are advertised (short 2s wait).
    bool wait_for_clients(const std::string & wheel_id, const WheelClients & clients);

    // Synchronous service call from inside a MultiThreadedExecutor callback.
    // Wait on the future only (other threads process the reply). Do not nest
    // spin_until_future_complete — illegal while this node is already spinning.
    template<typename ServiceT>
    typename ServiceT::Response::SharedPtr call_sync(
        const typename rclcpp::Client<ServiceT>::SharedPtr & client,
        const typename ServiceT::Request::SharedPtr & request,
        std::chrono::seconds timeout);

    // Handler for ~/set_closed_loop — see class comment above.
    void handle_set_closed_loop(
        const std::shared_ptr<std_srvs::srv::SetBool::Request> request,
        std::shared_ptr<std_srvs::srv::SetBool::Response> response);

    // Shared body for ~/calibrate_<id> Trigger services.
    void handle_calibrate(
        const std::string & wheel_id,
        const std::shared_ptr<std_srvs::srv::Trigger::Request> request,
        std::shared_ptr<std_srvs::srv::Trigger::Response> response);

    std::vector<std::string> wheel_ids_;
    std::string can_interface_;  // forwarded to commission_wheels --can
    std::mutex busy_mutex_;      // try_lock across CLOSED_LOOP + calibrate handlers
    // Callback group that allows overlapping callbacks (ROS type name:
    // CallbackGroupType::Reentrant). Needed because handlers block inside
    // call_sync / std::system; without it the executor can deadlock waiting
    // for a reply that never gets spun. Pair with MultiThreadedExecutor in main.
    rclcpp::CallbackGroup::SharedPtr cb_group_;
    std::unordered_map<std::string, WheelClients> clients_;
    rclcpp::Service<std_srvs::srv::SetBool>::SharedPtr set_closed_loop_srv_;
    std::vector<rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr> calibrate_srvs_;
};
