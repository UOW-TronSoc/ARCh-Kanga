#pragma once

#include <cstdint>
#include <optional>

namespace kanga_core_controller
{

// Converts timestamps from the node clock into safe controller time steps.
// A first sample, a backwards / zero jump, or an unexpectedly large jump
// resets the baseline and returns no step. This keeps acceleration state from
// advancing while simulated time is paused or reset.
class ControlTimeStep
{
public:
  explicit ControlTimeStep(double maximum_step_s);

  std::optional<double> update(std::int64_t now_nanoseconds);
  void reset();

private:
  std::int64_t maximum_step_nanoseconds_;
  std::int64_t previous_nanoseconds_{0};
  bool initialized_{false};
};

}  // namespace kanga_core_controller
