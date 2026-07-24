#include "kanga_core_drive/drive_manager.hpp"

#include <cctype>
#include <chrono>
#include <cstdlib>
#include <sstream>

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

}  // namespace

DriveManager::DriveManager(const rclcpp::NodeOptions & options)
: Node("drive_manager", options)
{
    // wheel_ids / can_interface come from launch (wheels.launch.py).
    // can_interface is forwarded into calibrate_* → commission_wheels.
    this->declare_parameter<std::vector<std::string>>(
        "wheel_ids", {"fl", "bl", "br", "fr"});
    this->declare_parameter<std::string>("can_interface", "can_core");

    wheel_ids_ = this->get_parameter("wheel_ids").as_string_array();
    can_interface_ = this->get_parameter("can_interface").as_string();
    for (auto & id : wheel_ids_) {
        id = to_lower(id);
    }

    // Allow overlapping callbacks in this group (ROS calls this "Reentrant").
    // Handlers block waiting on wheel services / shelling commission; if the
    // group were mutually exclusive, the reply callback could never run and
    // we'd deadlock. MultiThreadedExecutor in main spins the other work.
    cb_group_ = this->create_callback_group(rclcpp::CallbackGroupType::Reentrant);

    // One client pair per wheel under /wheel_<id>/… (custom_odrive_node services).
    // Intentionally no set_enabled clients — stop is /drivestop, not latching enable.
    for (const auto & wid : wheel_ids_) {
        const std::string ns = "/wheel_" + wid;
        WheelClients clients;
        // /wheel_<id>/clear_errors — clear ODrive sticky faults before arming.
        clients.clear_errors = this->create_client<std_srvs::srv::Empty>(
            ns + "/clear_errors", rmw_qos_profile_services_default, cb_group_);
        // /wheel_<id>/request_axis_state — set IDLE (1) or CLOSED_LOOP (8).
        clients.axis_state = this->create_client<custom_odrive::srv::AxisState>(
            ns + "/request_axis_state", rmw_qos_profile_services_default, cb_group_);
        clients_[wid] = clients;
    }

    // Service: arm all wheels (true) or idle all wheels (false). See header.
    set_closed_loop_srv_ = this->create_service<std_srvs::srv::SetBool>(
        "~/set_closed_loop",
        std::bind(
            &DriveManager::handle_set_closed_loop, this, std::placeholders::_1,
            std::placeholders::_2),
        rmw_qos_profile_services_default, cb_group_);

    // One Trigger per wheel — basestation can bind one button → one service.
    for (const auto & wid : wheel_ids_) {
        const std::string name = "~/calibrate_" + wid;
        calibrate_srvs_.push_back(
            this->create_service<std_srvs::srv::Trigger>(
                name,
                [this, wid](
                    const std::shared_ptr<std_srvs::srv::Trigger::Request> request,
                    std::shared_ptr<std_srvs::srv::Trigger::Response> response) {
                    this->handle_calibrate(wid, request, response);
                },
                rmw_qos_profile_services_default, cb_group_));
    }

    RCLCPP_INFO(this->get_logger(), "drive_manager ready (%zu wheels)", wheel_ids_.size());
}

bool DriveManager::wait_for_clients(const std::string & wheel_id, const WheelClients & clients)
{
    // Helper: confirm this wheel's clear_errors + request_axis_state exist.
    // Short wait — if custom_odrive_node is down, fail the request, don't hang.
    const std::string ns = "/wheel_" + wheel_id;
    if (!clients.clear_errors->wait_for_service(2s)) {
        RCLCPP_ERROR(this->get_logger(), "Service not available: %s/clear_errors", ns.c_str());
        return false;
    }
    if (!clients.axis_state->wait_for_service(2s)) {
        RCLCPP_ERROR(this->get_logger(), "Service not available: %s/request_axis_state", ns.c_str());
        return false;
    }
    return true;
}

template<typename ServiceT>
typename ServiceT::Response::SharedPtr DriveManager::call_sync(
    const typename rclcpp::Client<ServiceT>::SharedPtr & client,
    const typename ServiceT::Request::SharedPtr & request,
    std::chrono::seconds timeout)
{
    // Helper: call a ROS service and wait in-place for the response (or timeout).
    // Needs MultiThreadedExecutor + overlapping callback group (see constructor)
    // so the reply can be processed while we are blocked here.
    auto future = client->async_send_request(request);
    const auto ret = rclcpp::spin_until_future_complete(
        this->get_node_base_interface(), future, timeout);
    if (ret != rclcpp::FutureReturnCode::SUCCESS) {
        return nullptr;
    }
    return future.get();
}

void DriveManager::handle_set_closed_loop(
    const std::shared_ptr<std_srvs::srv::SetBool::Request> request,
    std::shared_ptr<std_srvs::srv::SetBool::Response> response)
{
    // ~/set_closed_loop handler: true → CLOSED_LOOP all wheels; false → IDLE all.
    // try_lock: refuse overlapping arm/calibrate rather than queue long work.
    std::unique_lock<std::mutex> lock(busy_mutex_, std::try_to_lock);
    if (!lock.owns_lock()) {
        response->success = false;
        response->message = "busy";
        return;
    }

    const bool enable = request->data;
    std::ostringstream messages;

    // Fail the whole request if any wheel cannot transition; earlier wheels may
    // already have changed state — operator should retry or idle explicitly.
    for (const auto & wid : wheel_ids_) {
        auto & clients = clients_.at(wid);
        if (!wait_for_clients(wid, clients)) {
            response->success = false;
            response->message = "services missing for " + wid;
            return;
        }

        if (enable) {
            // Clear sticky faults before CLOSED_LOOP so a prior trip does not
            // immediately bounce the axis back out.
            auto clear_req = std::make_shared<std_srvs::srv::Empty::Request>();
            call_sync<std_srvs::srv::Empty>(clients.clear_errors, clear_req, 5s);

            auto ax_req = std::make_shared<custom_odrive::srv::AxisState::Request>();
            ax_req->axis_requested_state = kAxisClosedLoop;
            auto ax_res = call_sync<custom_odrive::srv::AxisState>(
                clients.axis_state, ax_req, 15s);
            if (!ax_res || !ax_res->success) {
                response->success = false;
                response->message = "CLOSED_LOOP failed for " + wid;
                return;
            }
            if (!messages.str().empty()) {
                messages << ", ";
            }
            messages << wid << ":closed_loop";
        } else {
            // Soft idle only — does not latch set_enabled. Use /drivestop for
            // an emergency/global stop of the setpoint path.
            auto ax_req = std::make_shared<custom_odrive::srv::AxisState::Request>();
            ax_req->axis_requested_state = kAxisIdle;
            call_sync<custom_odrive::srv::AxisState>(clients.axis_state, ax_req, 15s);

            if (!messages.str().empty()) {
                messages << ", ";
            }
            messages << wid << ":idle";
        }
    }

    response->success = true;
    response->message = messages.str();
}

void DriveManager::handle_calibrate(
    const std::string & wheel_id,
    const std::shared_ptr<std_srvs::srv::Trigger::Request> /*request*/,
    std::shared_ptr<std_srvs::srv::Trigger::Response> response)
{
    // ~/calibrate_<id> handler: one-wheel FULL_CALIBRATION via commission_wheels.
    // Basestation motor-status page: one button → one Trigger service.
    std::unique_lock<std::mutex> lock(busy_mutex_, std::try_to_lock);
    if (!lock.owns_lock()) {
        response->success = false;
        response->message = "busy";
        return;
    }

    // Shell out to the Python commission wrapper (Fibre apply + FULL_CALIBRATION).
    // Interactive prompts inside custom_odrive commission still apply on the TTY.
    std::ostringstream cmd;
    cmd << "ros2 run kanga_core_drive commission_wheels -- --wheels " << wheel_id
        << " --can " << can_interface_ << " --calibrate";
    RCLCPP_INFO(this->get_logger(), "Calibrating %s: %s", wheel_id.c_str(), cmd.str().c_str());
    const int rc = std::system(cmd.str().c_str());
    if (rc != 0) {
        response->success = false;
        response->message = "commission_wheels exited " + std::to_string(rc);
        return;
    }
    response->success = true;
    response->message = "calibrated " + wheel_id;
}

// Explicit instantiations for the two service types we call synchronously.
template std_srvs::srv::Empty::Response::SharedPtr
DriveManager::call_sync<std_srvs::srv::Empty>(
    const rclcpp::Client<std_srvs::srv::Empty>::SharedPtr &,
    const std_srvs::srv::Empty::Request::SharedPtr &,
    std::chrono::seconds);

template custom_odrive::srv::AxisState::Response::SharedPtr
DriveManager::call_sync<custom_odrive::srv::AxisState>(
    const rclcpp::Client<custom_odrive::srv::AxisState>::SharedPtr &,
    const custom_odrive::srv::AxisState::Request::SharedPtr &,
    std::chrono::seconds);
