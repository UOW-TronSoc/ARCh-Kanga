#include "kanga_core_battery/bms_can_node.hpp"

#include <memory>

#include "rclcpp/rclcpp.hpp"

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);

  auto node = std::make_shared<BMSCanNode>("bms_can_node");
  rclcpp::spin(node);

  rclcpp::shutdown();
  return 0;
}
