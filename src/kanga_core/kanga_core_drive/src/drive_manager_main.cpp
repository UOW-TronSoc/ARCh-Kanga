#include "kanga_core_drive/drive_manager.hpp"

#include <memory>

#include "rclcpp/executors/multi_threaded_executor.hpp"

int main(int argc, char ** argv)
{
    rclcpp::init(argc, argv);
    auto node = std::make_shared<DriveManager>();
    // Several threads: handlers block waiting on wheel replies / commission.
    // Overlapping-callback group (ROS: "Reentrant") needs another thread free
    // to process those replies, otherwise call_sync deadlocks.
    rclcpp::executors::MultiThreadedExecutor executor(rclcpp::ExecutorOptions(), 4);
    executor.add_node(node);
    executor.spin();
    rclcpp::shutdown();
    return 0;
}
