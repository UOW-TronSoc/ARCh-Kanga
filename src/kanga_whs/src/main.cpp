#include <memory>
#include <string>
#include <vector>

#include "kanga_whs/whs_node.hpp"
#include "rclcpp/rclcpp.hpp"

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);

  // Forward launch remappings (__ns, __node, …) into the node.
  rclcpp::NodeOptions options;
  options.arguments(std::vector<std::string>(argv, argv + argc));

  rclcpp::spin(std::make_shared<kanga_whs::WhsNode>("whs_node", options));
  rclcpp::shutdown();
  return 0;
}
