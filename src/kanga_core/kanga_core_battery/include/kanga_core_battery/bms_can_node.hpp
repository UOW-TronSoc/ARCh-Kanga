#ifndef KANGA_CORE_BATTERY__BMS_CAN_NODE_HPP_
#define KANGA_CORE_BATTERY__BMS_CAN_NODE_HPP_

#include <cstdint>
#include <mutex>
#include <string>

#include "can_msgs/msg/frame.hpp"
#include "kanga_interfaces/msg/battery_info.hpp"
#include "kanga_interfaces/msg/bms_status.hpp"
#include "rclcpp/rclcpp.hpp"

using BatteryInfo = kanga_interfaces::msg::BatteryInfo;
using BmsStatus = kanga_interfaces::msg::BmsStatus;

// Reads the rover BMS over a ros2_socketcan bridge and publishes battery topics.
// See the package README for how the topics fit together.
class BMSCanNode : public rclcpp::Node
{
public:
  // Sets up parameters, publishers/subscribers, and timers.
  explicit BMSCanNode(const std::string & node_name);

private:
  // -------------------------------------------------------------------------
  // Ready flags: each decoded BMS reply sets a bit. Publish when all are set.
  // -------------------------------------------------------------------------
  static const int16_t kBatteryInfoVoltageCurrentSocReady = 0b0001;  // cmd 0x90
  static const int16_t kBatteryInfoCapacityReady = 0b0010;           // cmd 0x93
  static const int16_t kBatteryInfoReadyMask =
    kBatteryInfoVoltageCurrentSocReady | kBatteryInfoCapacityReady;

  static const int16_t kBMSStatusTemperaturesReady = 0b001;  // cmd 0x92
  static const int16_t kBMSStatusFaultBitsReady = 0b010;     // cmd 0x98
  static const int16_t kBMSStatusChargeStateReady = 0b100;   // cmd 0x93
  static const int16_t kBMSStatusReadyMask =
    kBMSStatusTemperaturesReady | kBMSStatusFaultBitsReady |
    kBMSStatusChargeStateReady;

  static constexpr int kResponseTimeoutMs = 250;    // wait before retrying a request
  static constexpr int kMaxRequestAttempts = 3;     // initial request plus two retries
  static constexpr int kWarningThrottleMs = 5000;   // limit repeated offline warnings
  static constexpr int kPublishFlushMs = 20;        // how often we try to publish
  static constexpr int kNumPollCommands = 4;        // length of kPollCommands[]

  // Called when a CAN Frame arrives from the ros2_socketcan bridge.
  void on_can_frame(const can_msgs::msg::Frame::SharedPtr msg);

  // Starts one full round of BMS requests (called every req_period_ seconds).
  void start_poll_cycle();

  // Sends the current request and starts its response timeout.
  void send_current_request();

  // Retries a missed request or advances after its attempts are exhausted.
  void on_request_timeout();

  // Advances to the next command after a reply or exhausted retries.
  void advance_to_next_request();

  // Publishes BatteryInfo / BmsStatus when all required fields have arrived.
  void flush_ready_messages();

  // Builds the 29-bit extended CAN ID used by this BMS protocol.
  uint32_t build_extended_id(uint8_t command, int node_id);

  // Returns false (and warns) if the frame byte count is wrong.
  bool verify_frame_length(const std::string & name, uint8_t expected, uint8_t length);

  // ---- ROS parameters ----
  int local_node_id_;       // our address in TX CAN IDs (default 320)
  int bms_node_id_;         // BMS address filter for RX (default 16385)
  std::string interface_;   // CAN bus name / topic prefix (default "can1")
  int req_period_;          // seconds between poll cycles (default 1)

  // ---- Poll sequencer state ----
  int poll_command_index_;          // current request in the poll list
  int request_attempt_;             // attempts made for the current request
  bool poll_cycle_active_;          // prevents overlapping poll cycles

  // ---- Aggregated BatteryInfo ----
  int16_t battery_info_ready_flags_;
  std::mutex battery_info_mutex_;
  BatteryInfo battery_info_;
  rclcpp::Publisher<BatteryInfo>::SharedPtr battery_info_publisher_;

  // ---- Aggregated BmsStatus ----
  int16_t bms_status_ready_flags_;
  std::mutex bms_status_mutex_;
  BmsStatus bms_status_;
  rclcpp::Publisher<BmsStatus>::SharedPtr bms_status_publisher_;

  // ---- Bridge Frame pub/sub ----
  rclcpp::Publisher<can_msgs::msg::Frame>::SharedPtr can_tx_publisher_;
  rclcpp::Subscription<can_msgs::msg::Frame>::SharedPtr can_rx_subscription_;

  // ---- Timers ----
  rclcpp::TimerBase::SharedPtr poll_cycle_timer_;       // starts each poll round
  rclcpp::TimerBase::SharedPtr request_timeout_timer_;  // retries missing replies
  rclcpp::TimerBase::SharedPtr publish_flush_timer_;    // checks ready flags
};

#endif  // KANGA_CORE_BATTERY__BMS_CAN_NODE_HPP_
