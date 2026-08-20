// BMS CAN client for Kanga.
//
// Vendor protocol PDF: docs/reference/Daly-CAN-Communications-Protocol-V1.0.pdf
// Package overview:    src/kanga_core/kanga_core_battery/README.md
//
// Flow:
//   start_poll_cycle / send_next_request  -> ask the BMS for data
//   on_can_frame                          -> decode replies
//   flush_ready_messages                  -> publish when a full set is ready

#include "kanga_core_battery/bms_can_node.hpp"

#include <chrono>
#include <functional>

using std::placeholders::_1;

namespace
{

// Commands we request each poll cycle (others like 0x91/0x94 are unused).
const uint8_t kPollCommands[4] = {
  0x90,  // voltage, current, SOC
  0x92,  // temperatures
  0x93,  // charge state + capacity
  0x98,  // fault bytes
};

// Read a big-endian 16-bit value (BMS protocol byte order).
uint16_t read_u16_be(const uint8_t * data)
{
  return static_cast<uint16_t>((static_cast<uint16_t>(data[0]) << 8) | data[1]);
}

// Read a big-endian 32-bit value (BMS protocol byte order).
uint32_t read_u32_be(const uint8_t * data)
{
  return (static_cast<uint32_t>(data[0]) << 24) |
         (static_cast<uint32_t>(data[1]) << 16) |
         (static_cast<uint32_t>(data[2]) << 8) |
         static_cast<uint32_t>(data[3]);
}

// Pull the command byte out of a 29-bit BMS CAN ID (bits 16..23).
uint8_t command_id_from_can_id(uint32_t can_id)
{
  return static_cast<uint8_t>((can_id >> 16) & 0xFF);
}

// Pull the address word out of a 29-bit BMS CAN ID (low 16 bits).
uint16_t address_word_from_can_id(uint32_t can_id)
{
  return static_cast<uint16_t>(can_id & 0xFFFF);
}

}  // namespace

// ---------------------------------------------------------------------------
// Constructor: parameters, pubs/subs, timers
// ---------------------------------------------------------------------------
BMSCanNode::BMSCanNode(const std::string & node_name)
: rclcpp::Node(node_name)
{
  // --- ROS parameters ---
  // Launch may override interface / req_period. Node IDs use these defaults.
  this->declare_parameter<int>("local_node_id", 320);       // 0x0140
  this->declare_parameter<int>("bms_node_id", 16385);       // 0x4001
  this->declare_parameter<std::string>("interface", "can1");
  this->declare_parameter<int>("req_period", 1);            // seconds

  this->get_parameter("local_node_id", local_node_id_);
  this->get_parameter("bms_node_id", bms_node_id_);
  this->get_parameter("interface", interface_);
  this->get_parameter("req_period", req_period_);

  // --- Battery topic publishers ---
  rclcpp::QoS publisher_qos(10);
  battery_info_publisher_ =
    this->create_publisher<BatteryInfo>("battery_info", publisher_qos);
  bms_status_publisher_ =
    this->create_publisher<BmsStatus>("bms_status", publisher_qos);

  // --- CAN Frame topics (absolute, e.g. /can1/from_can_bus) ---
  const std::string from_can_bus = "/" + interface_ + "/from_can_bus";
  const std::string to_can_bus = "/" + interface_ + "/to_can_bus";

  can_tx_publisher_ =
    this->create_publisher<can_msgs::msg::Frame>(to_can_bus, 50);
  can_rx_subscription_ = this->create_subscription<can_msgs::msg::Frame>(
    from_can_bus, 50,
    std::bind(&BMSCanNode::on_can_frame, this, _1));

  RCLCPP_INFO(
    this->get_logger(), "BMS Frame topics: sub %s  pub %s",
    from_can_bus.c_str(), to_can_bus.c_str());

  // --- Timers ---
  // Poll cycle: every req_period_ seconds, start asking for all commands again.
  poll_cycle_timer_ = this->create_wall_timer(
    std::chrono::seconds(req_period_),
    std::bind(&BMSCanNode::start_poll_cycle, this));

  // Response timeout: retry a request if its matching reply does not arrive.
  request_timeout_timer_ = this->create_wall_timer(
    std::chrono::milliseconds(kResponseTimeoutMs),
    std::bind(&BMSCanNode::on_request_timeout, this));
  request_timeout_timer_->cancel();

  // Flush: often check whether we have enough decoded fields to publish.
  publish_flush_timer_ = this->create_wall_timer(
    std::chrono::milliseconds(kPublishFlushMs),
    std::bind(&BMSCanNode::flush_ready_messages, this));

  poll_command_index_ = 0;
  request_attempt_ = 0;
  poll_cycle_active_ = false;
  battery_info_ready_flags_ = 0;
  bms_status_ready_flags_ = 0;
}

// ---------------------------------------------------------------------------
// Polling: ask the BMS for data
// ---------------------------------------------------------------------------

// Begin one poll round unless the previous round is still waiting for replies.
void BMSCanNode::start_poll_cycle()
{
  if (poll_cycle_active_) {
    RCLCPP_DEBUG(this->get_logger(), "Previous BMS poll cycle is still active");
    return;
  }

  poll_cycle_active_ = true;
  poll_command_index_ = 0;
  request_attempt_ = 0;
  send_current_request();
}

// Publish one empty request Frame for the current command.
void BMSCanNode::send_current_request()
{
  if (!poll_cycle_active_ || poll_command_index_ >= kNumPollCommands) {
    return;
  }

  const uint8_t command = kPollCommands[poll_command_index_];
  request_attempt_ = request_attempt_ + 1;

  can_msgs::msg::Frame frame;
  frame.header.stamp = this->now();
  frame.id = build_extended_id(command, local_node_id_);
  frame.is_rtr = false;
  frame.is_extended = true;
  frame.is_error = false;
  frame.dlc = 8;
  for (int i = 0; i < 8; ++i) {
    frame.data[i] = 0;
  }

  can_tx_publisher_->publish(frame);
  RCLCPP_DEBUG(
    this->get_logger(), "Sent BMS request 0x%02X (attempt %d/%d)",
    command, request_attempt_, kMaxRequestAttempts);
  request_timeout_timer_->reset();
}

// Retry the current command, then move on if the BMS remains silent.
void BMSCanNode::on_request_timeout()
{
  request_timeout_timer_->cancel();
  if (!poll_cycle_active_) {
    return;
  }

  if (request_attempt_ < kMaxRequestAttempts) {
    send_current_request();
    return;
  }

  RCLCPP_WARN_THROTTLE(
    this->get_logger(), *this->get_clock(), kWarningThrottleMs,
    "No BMS response to command 0x%02X after %d attempts",
    kPollCommands[poll_command_index_], kMaxRequestAttempts);
  advance_to_next_request();
}

// Stop the timeout and either request the next command or finish the cycle.
void BMSCanNode::advance_to_next_request()
{
  request_timeout_timer_->cancel();
  poll_command_index_ = poll_command_index_ + 1;
  request_attempt_ = 0;

  if (poll_command_index_ >= kNumPollCommands) {
    poll_cycle_active_ = false;
    return;
  }

  send_current_request();
}

// ---------------------------------------------------------------------------
// RX: decode Frames from the bridge
// ---------------------------------------------------------------------------

// Ignore non-BMS traffic; decode matching replies into battery_info_ / bms_status_.
void BMSCanNode::on_can_frame(const can_msgs::msg::Frame::SharedPtr msg)
{
  // Only care about extended data frames from our BMS address.
  if (msg->is_error || msg->is_rtr || !msg->is_extended) {
    return;
  }
  if (address_word_from_can_id(msg->id) != bms_node_id_) {
    return;
  }

  const uint8_t command = command_id_from_can_id(msg->id);
  const bool is_expected_response =
    poll_cycle_active_ && poll_command_index_ < kNumPollCommands &&
    command == kPollCommands[poll_command_index_];
  bool response_complete = false;

  switch (command) {
    case 0x90: {
      // Pack voltage, current, SOC.
      // [cum V][gather V][current][SOC]; V/SOC *0.1; current (raw-30000)*0.1 A
      if (!verify_frame_length("TotalVoltageCurrentSoc", 8, msg->dlc)) {
        break;
      }
      std::lock_guard<std::mutex> lock(battery_info_mutex_);
      battery_info_.total_voltage = read_u16_be(&msg->data[0]) * 0.1f;
      battery_info_.measured_voltage = read_u16_be(&msg->data[2]) * 0.1f;
      battery_info_.current = (read_u16_be(&msg->data[4]) - 30000) * 0.1f;
      battery_info_.soc = read_u16_be(&msg->data[6]) * 0.1f;
      battery_info_ready_flags_ |= kBatteryInfoVoltageCurrentSocReady;
      response_complete = true;
      break;
    }

    case 0x93: {
      // Charge/discharge state + remaining capacity.
      // Byte0: 0=stationary, 1=charge, 2=discharge. Bytes4-7: capacity mAh.
      if (!verify_frame_length("ChargeDischargeState", 8, msg->dlc)) {
        break;
      }
      std::lock_guard<std::mutex> info_lock(battery_info_mutex_);
      std::lock_guard<std::mutex> status_lock(bms_status_mutex_);
      bms_status_.charge_state = msg->data[0];
      battery_info_.capacity = read_u32_be(&msg->data[4]);
      battery_info_ready_flags_ |= kBatteryInfoCapacityReady;
      bms_status_ready_flags_ |= kBMSStatusChargeStateReady;
      response_complete = true;
      break;
    }

    case 0x92: {
      // Max and min temperatures (deg C = raw - 40).
      if (!verify_frame_length("MaxMinTemperature", 8, msg->dlc)) {
        break;
      }
      std::lock_guard<std::mutex> lock(bms_status_mutex_);
      bms_status_.temps[0] = msg->data[0] - 40;
      bms_status_.temps[1] = msg->data[2] - 40;
      bms_status_ready_flags_ |= kBMSStatusTemperaturesReady;
      response_complete = true;
      break;
    }

    case 0x98: {
      // Raw fault status bytes (bit meanings in the protocol PDF).
      if (!verify_frame_length("BatteryFaultStatus", 8, msg->dlc)) {
        break;
      }
      std::lock_guard<std::mutex> lock(bms_status_mutex_);
      for (int i = 0; i < 8; ++i) {
        bms_status_.fault_bits[i] = msg->data[i];
      }
      bms_status_ready_flags_ |= kBMSStatusFaultBitsReady;
      response_complete = true;
      break;
    }

    default:
      break;
  }

  if (response_complete && is_expected_response) {
    advance_to_next_request();
  }
}

// ---------------------------------------------------------------------------
// Publish when a full message set is ready
// ---------------------------------------------------------------------------

// If every required field bit is set, publish and clear the flags.
void BMSCanNode::flush_ready_messages()
{
  {
    std::lock_guard<std::mutex> lock(battery_info_mutex_);
    if ((battery_info_ready_flags_ & kBatteryInfoReadyMask) == kBatteryInfoReadyMask) {
      battery_info_.header.stamp = this->now();
      battery_info_publisher_->publish(battery_info_);
      battery_info_ready_flags_ = 0;
    }
  }
  {
    std::lock_guard<std::mutex> lock(bms_status_mutex_);
    if ((bms_status_ready_flags_ & kBMSStatusReadyMask) == kBMSStatusReadyMask) {
      bms_status_.header.stamp = this->now();
      bms_status_publisher_->publish(bms_status_);
      bms_status_ready_flags_ = 0;
    }
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// Pack priority | command | address into one extended CAN ID.
uint32_t BMSCanNode::build_extended_id(uint8_t command, int node_id)
{
  // Example: cmd 0x90, local 320 (0x0140) -> 0x18900140
  return (0x18u << 24) |
         (static_cast<uint32_t>(command) << 16) |
         static_cast<uint32_t>(node_id & 0xFFFF);
}

// Check that the Frame has the expected number of data bytes.
bool BMSCanNode::verify_frame_length(
  const std::string & name, uint8_t expected, uint8_t length)
{
  if (expected == length) {
    return true;
  }
  RCLCPP_WARN(
    this->get_logger(), "Incorrect %s frame length: %u != %u",
    name.c_str(), length, expected);
  return false;
}
