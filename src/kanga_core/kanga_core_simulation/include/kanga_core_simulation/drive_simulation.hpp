#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>

namespace kanga_core_simulation
{

constexpr std::size_t kWheelCount = 4;
using WheelVector = std::array<double, kWheelCount>;

// Canonical public-message order, shared with WheelVelocityCommand.
WheelVector wheel_vector(
  double front_left_rad_s,
  double back_left_rad_s,
  double back_right_rad_s,
  double front_right_rad_s);

enum class SimDriveMode
{
  kIdle,
  kClosedLoop,
};

// ROS-facing drive state with the same enable, stop, and watchdog semantics as
// the physical drive boundary. Callers provide simulation time explicitly.
class SimDriveState
{
public:
  explicit SimDriveState(double command_timeout_s);

  bool request_closed_loop(bool enable, std::string & message);
  void set_drivestop(bool active);
  bool accept_command(const WheelVector & command, std::int64_t sim_time_ns);
  bool actuation_enabled(std::int64_t sim_time_ns);

  bool drivestop_active() const;
  SimDriveMode mode() const;
  const WheelVector & command() const;

private:
  std::int64_t timeout_ns_;
  std::int64_t last_command_time_ns_{0};
  std::int64_t last_sim_time_ns_{0};
  WheelVector command_{};
  SimDriveMode mode_{SimDriveMode::kIdle};
  bool drivestop_active_{false};
  bool command_received_{false};
  bool sim_time_initialized_{false};
};

struct VelocityControllerConfig
{
  double proportional_gain{0.0};
  double integral_gain{0.0};
  double derivative_gain{0.0};
  double integral_limit{0.0};
  double torque_limit_nm{0.0};
  double velocity_limit_rad_s{0.0};
  double acceleration_limit_rad_s2{0.0};
};

// Four independent velocity loops with a shared configuration. Wheel targets
// remain atomic, but effort is calculated per physical joint.
class WheelVelocityController
{
public:
  explicit WheelVelocityController(VelocityControllerConfig config);

  WheelVector update(
    const WheelVector & requested_velocity,
    const WheelVector & measured_velocity,
    double elapsed_time_s,
    bool enabled);
  void reset();

  const WheelVector & limited_targets() const;

private:
  VelocityControllerConfig config_;
  WheelVector targets_{};
  WheelVector integral_errors_{};
  WheelVector previous_errors_{};
  bool error_history_valid_{false};
};

}  // namespace kanga_core_simulation
