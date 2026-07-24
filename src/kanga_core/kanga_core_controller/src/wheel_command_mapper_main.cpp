#include "kanga_core_controller/wheel_command_mapper.hpp"

#include "rclcpp/rclcpp.hpp"

// Standard ROS 2 C++ entrypoint: init → make node → spin until Ctrl-C → shutdown.
int main(int argc, char ** argv)
{
    rclcpp::init(argc, argv);
    auto node = std::make_shared<WheelCommandMapper>();
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}
