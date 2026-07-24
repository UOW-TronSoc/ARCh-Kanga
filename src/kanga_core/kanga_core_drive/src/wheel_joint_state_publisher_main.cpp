#include "kanga_core_drive/wheel_joint_state_publisher.hpp"

#include <memory>

int main(int argc, char ** argv)
{
    rclcpp::init(argc, argv);
    auto node = std::make_shared<WheelJointStatePublisher>();
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}
