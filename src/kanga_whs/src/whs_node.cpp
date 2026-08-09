#include "kanga_whs/whs_node.hpp"

#include <functional>

namespace kanga_whs
{

WhsNode::WhsNode(const std::string & node_name, const rclcpp::NodeOptions & options)
: Node(node_name, options)
{
  // Match custom_odrive /drivestop subscription: KeepLast(1), reliable, transient_local.
  rclcpp::QoS drivestop_qos(rclcpp::KeepLast(1));
  drivestop_qos.reliable();
  drivestop_qos.transient_local();
  drivestop_publisher_ = create_publisher<Bool>("/drivestop", drivestop_qos);

  // Private service → /<node_name>/set_drivestop
  set_drivestop_service_ = create_service<SetBool>(
    "~/set_drivestop",
    std::bind(
      &WhsNode::set_drivestop_callback, this,
      std::placeholders::_1, std::placeholders::_2));

  // Publish initial allow so late-joining consumers see an authoritative WHS value.
  publish_drivestop(false);

  RCLCPP_INFO(
    get_logger(),
    "WHS ready: service ~/set_drivestop (true=stop, false=allow) → /drivestop");
}

void WhsNode::set_drivestop_callback(
  const std::shared_ptr<SetBool::Request> request,
  std::shared_ptr<SetBool::Response> response)
{
  const bool active = request->data;
  publish_drivestop(active);
  response->success = true;
  response->message = active ? "drivestop asserted (stop)" : "drivestop cleared (allow)";
  RCLCPP_WARN(get_logger(), "%s", response->message.c_str());
}

void WhsNode::publish_drivestop(bool active)
{
  drivestop_active_.store(active);
  Bool msg;
  msg.data = active;
  drivestop_publisher_->publish(msg);
}

}  // namespace kanga_whs
