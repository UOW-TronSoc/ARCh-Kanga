#include "kanga_core_simulation/drive_simulation.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace kanga_core_simulation
{
namespace
{

bool finite_vector(const WheelVector & values)
{
  return std::all_of(
    values.begin(), values.end(),
    [](const double value) {return std::isfinite(value);});
}

double require_positive(const double value, const char * name)
{
  if (!std::isfinite(value) || value <= 0.0) {
    throw std::invalid_argument(std::string(name) + " must be finite and > 0");
  }
  return value;
}

double require_nonnegative(const double value, const char * name)
{
  if (!std::isfinite(value) || value < 0.0) {
    throw std::invalid_argument(std::string(name) + " must be finite and >= 0");
  }
  return value;
}

}  // namespace

WheelVector wheel_vector(
  const double front_left_rad_s,
  const double back_left_rad_s,
  const double back_right_rad_s,
  const double front_right_rad_s)
{
  return {
    front_left_rad_s,
    back_left_rad_s,
    back_right_rad_s,
    front_right_rad_s,
  };
}

SimDriveState::SimDriveState(const double command_timeout_s)
{
  require_positive(command_timeout_s, "command_timeout_s");
  const double timeout_ns = command_timeout_s * 1e9;
  if (timeout_ns > static_cast<double>(std::numeric_limits<std::int64_t>::max())) {
    throw std::invalid_argument("command_timeout_s is too large");
  }
  timeout_ns_ = static_cast<std::int64_t>(timeout_ns);
}

bool SimDriveState::request_closed_loop(
  const bool enable, std::string & message)
{
  if (!enable) {
    mode_ = SimDriveMode::kIdle;
    message = "all wheels idle";
    return true;
  }
  if (drivestop_active_) {
    mode_ = SimDriveMode::kIdle;
    message = "drivestop is active";
    return false;
  }

  mode_ = SimDriveMode::kClosedLoop;
  message = "all simulated wheels in closed loop";
  return true;
}

void SimDriveState::set_drivestop(const bool active)
{
  drivestop_active_ = active;
  if (active) {
    mode_ = SimDriveMode::kIdle;
    command_received_ = false;
    command_.fill(0.0);
  }
}

bool SimDriveState::accept_command(
  const WheelVector & command, const std::int64_t sim_time_ns)
{
  if (!finite_vector(command)) {
    return false;
  }
  command_ = command;
  last_command_time_ns_ = sim_time_ns;
  command_received_ = true;
  return true;
}

bool SimDriveState::actuation_enabled(const std::int64_t sim_time_ns)
{
  if (sim_time_initialized_ && sim_time_ns < last_sim_time_ns_) {
    mode_ = SimDriveMode::kIdle;
    command_received_ = false;
    command_.fill(0.0);
  }
  last_sim_time_ns_ = sim_time_ns;
  sim_time_initialized_ = true;

  if (drivestop_active_ || mode_ != SimDriveMode::kClosedLoop ||
    !command_received_)
  {
    return false;
  }

  const std::int64_t command_age_ns = sim_time_ns - last_command_time_ns_;
  if (command_age_ns < 0 || command_age_ns > timeout_ns_) {
    mode_ = SimDriveMode::kIdle;
    command_received_ = false;
    command_.fill(0.0);
    return false;
  }
  return true;
}

bool SimDriveState::drivestop_active() const
{
  return drivestop_active_;
}

SimDriveMode SimDriveState::mode() const
{
  return mode_;
}

const WheelVector & SimDriveState::command() const
{
  return command_;
}

WheelVelocityController::WheelVelocityController(
  const VelocityControllerConfig config)
: config_(config)
{
  require_positive(config_.proportional_gain, "proportional_gain");
  require_nonnegative(config_.integral_gain, "integral_gain");
  require_nonnegative(config_.derivative_gain, "derivative_gain");
  require_nonnegative(config_.integral_limit, "integral_limit");
  require_positive(config_.torque_limit_nm, "torque_limit_nm");
  require_positive(config_.velocity_limit_rad_s, "velocity_limit_rad_s");
  require_positive(config_.acceleration_limit_rad_s2, "acceleration_limit_rad_s2");
}

WheelVector WheelVelocityController::update(
  const WheelVector & requested_velocity,
  const WheelVector & measured_velocity,
  const double elapsed_time_s,
  const bool enabled)
{
  WheelVector efforts{};
  if (!enabled) {
    reset();
    return efforts;
  }
  if (!finite_vector(requested_velocity) || !finite_vector(measured_velocity) ||
    !std::isfinite(elapsed_time_s) || elapsed_time_s <= 0.0)
  {
    return efforts;
  }

  const double maximum_delta = config_.acceleration_limit_rad_s2 * elapsed_time_s;
  for (std::size_t index = 0; index < kWheelCount; ++index) {
    const double request = std::clamp(
      requested_velocity[index], -config_.velocity_limit_rad_s,
      config_.velocity_limit_rad_s);
    targets_[index] += std::clamp(
      request - targets_[index], -maximum_delta, maximum_delta);

    const double error = targets_[index] - measured_velocity[index];
    integral_errors_[index] = std::clamp(
      integral_errors_[index] + error * elapsed_time_s,
      -config_.integral_limit, config_.integral_limit);
    const double derivative = error_history_valid_ ?
      (error - previous_errors_[index]) / elapsed_time_s : 0.0;
    previous_errors_[index] = error;
    efforts[index] = std::clamp(
      config_.proportional_gain * error +
      config_.integral_gain * integral_errors_[index] +
      config_.derivative_gain * derivative,
      -config_.torque_limit_nm, config_.torque_limit_nm);
  }
  error_history_valid_ = true;
  return efforts;
}

void WheelVelocityController::reset()
{
  targets_.fill(0.0);
  integral_errors_.fill(0.0);
  previous_errors_.fill(0.0);
  error_history_valid_ = false;
}

const WheelVector & WheelVelocityController::limited_targets() const
{
  return targets_;
}

}  // namespace kanga_core_simulation
