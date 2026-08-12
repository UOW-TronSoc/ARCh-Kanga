#ifndef KANGA_WHS__GPIO_STOP_INPUT_HPP_
#define KANGA_WHS__GPIO_STOP_INPUT_HPP_

namespace kanga_whs
{

/**
 * Placeholder for a future Jetson GPIO stop-switch reader.
 *
 * When implemented, this input should call the WHS SetBool service
 * (same API as CLI/GUI). It must not publish /drivestop itself and must not
 * become a second parallel control path inside WhsNode.
 *
 * Not wired in this iteration.
 */
class GpioStopInput
{
public:
  GpioStopInput() = default;

  /** Reserved: open GPIO and start sampling. No-op stub. */
  bool start() { return false; }

  /** Reserved: release GPIO. No-op stub. */
  void stop() {}

  /**
   * Reserved: return true when the physical switch requests stop.
   * Stub always reports "not requesting stop".
   */
  bool stop_requested() const { return false; }
};

}  // namespace kanga_whs

#endif  // KANGA_WHS__GPIO_STOP_INPUT_HPP_
