#include "kanga_core_controller/control_time_step.hpp"

#include <cmath>
#include <limits>
#include <stdexcept>

namespace kanga_core_controller
{

ControlTimeStep::ControlTimeStep(const double maximum_step_s)
{
  if (!std::isfinite(maximum_step_s) || maximum_step_s <= 0.0) {
    throw std::invalid_argument("maximum_step_s must be finite and > 0");
  }

  constexpr double kNanosecondsPerSecond = 1e9;
  const double maximum_step_nanoseconds = maximum_step_s * kNanosecondsPerSecond;
  if (maximum_step_nanoseconds >
    static_cast<double>(std::numeric_limits<std::int64_t>::max()))
  {
    throw std::invalid_argument("maximum_step_s is too large");
  }
  maximum_step_nanoseconds_ =
    static_cast<std::int64_t>(maximum_step_nanoseconds);
}

std::optional<double> ControlTimeStep::update(const std::int64_t now_nanoseconds)
{
  if (!initialized_) {
    previous_nanoseconds_ = now_nanoseconds;
    initialized_ = true;
    return std::nullopt;
  }

  const std::int64_t elapsed_nanoseconds = now_nanoseconds - previous_nanoseconds_;
  previous_nanoseconds_ = now_nanoseconds;
  if (elapsed_nanoseconds <= 0 || elapsed_nanoseconds > maximum_step_nanoseconds_) {
    return std::nullopt;
  }

  return static_cast<double>(elapsed_nanoseconds) / 1e9;
}

void ControlTimeStep::reset()
{
  initialized_ = false;
  previous_nanoseconds_ = 0;
}

}  // namespace kanga_core_controller
