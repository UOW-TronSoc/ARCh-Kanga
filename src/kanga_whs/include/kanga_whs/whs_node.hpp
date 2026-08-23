#ifndef KANGA_WHS__WHS_NODE_HPP_
#define KANGA_WHS__WHS_NODE_HPP_

#include <atomic>
#include <memory>
#include <string>

#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/bool.hpp"
#include "std_srvs/srv/set_bool.hpp"

namespace kanga_whs
{

/**
 * Owns the software whole-robot stop command published on /drivestop.
 *
 * Control API is a single SetBool service. External clients (CLI, future GPIO
 * watcher, GUI, etc.) call that service; they are not separate inputs inside
 * this package. Motor latching / enable behaviour stays in each consumer
 * (e.g. custom_odrive).
 *
 * Semantics match custom_odrive:
 *   true  → request stop (inhibit motion)
 *   false → allow motion again
 */
class WhsNode : public rclcpp::Node
{
public:
  explicit WhsNode(
    const std::string & node_name = "whs_node",
    const rclcpp::NodeOptions & options = rclcpp::NodeOptions());

private:
  using Bool = std_msgs::msg::Bool;
  using SetBool = std_srvs::srv::SetBool;

  void set_drivestop_callback(
    const std::shared_ptr<SetBool::Request> request,
    std::shared_ptr<SetBool::Response> response);

  void publish_drivestop(bool active);

  rclcpp::Publisher<Bool>::SharedPtr drivestop_publisher_;
  rclcpp::Service<SetBool>::SharedPtr set_drivestop_service_;

  // Last commanded software-stop state (not consumer latching).
  std::atomic<bool> drivestop_active_{true};
};

}  // namespace kanga_whs

#endif  // KANGA_WHS__WHS_NODE_HPP_
