#include <gtest/gtest.h>

#include <chrono>
#include <condition_variable>
#include <future>
#include <memory>
#include <mutex>
#include <string>
#include <thread>

#include "kanga_whs/whs_node.hpp"
#include "rclcpp/executors/multi_threaded_executor.hpp"
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/bool.hpp"
#include "std_srvs/srv/set_bool.hpp"

using namespace std::chrono_literals;

namespace
{

class RosContextFixture : public ::testing::Test
{
protected:
  static void SetUpTestSuite()
  {
    if (!rclcpp::ok()) {
      rclcpp::init(0, nullptr);
    }
  }

  static void TearDownTestSuite()
  {
    if (rclcpp::ok()) {
      rclcpp::shutdown();
    }
  }
};

TEST_F(RosContextFixture, PublishesFailSafeStartupAndRoutesServiceChanges)
{
  auto whs = std::make_shared<kanga_whs::WhsNode>("whs_node_test");
  auto observer = std::make_shared<rclcpp::Node>("whs_observer_test");

  std::mutex state_mutex;
  std::condition_variable state_changed;
  bool state_received = false;
  bool latest_state = false;

  rclcpp::QoS drivestop_qos(rclcpp::KeepLast(1));
  drivestop_qos.reliable();
  drivestop_qos.transient_local();
  const auto subscription = observer->create_subscription<std_msgs::msg::Bool>(
    "/drivestop", drivestop_qos,
    [&](const std_msgs::msg::Bool::SharedPtr message) {
      {
        std::lock_guard<std::mutex> lock(state_mutex);
        latest_state = message->data;
        state_received = true;
      }
      state_changed.notify_all();
    });
  const auto client = observer->create_client<std_srvs::srv::SetBool>(
    "/whs_node_test/set_drivestop");

  rclcpp::executors::MultiThreadedExecutor executor;
  executor.add_node(whs);
  executor.add_node(observer);
  std::thread spin_thread([&executor]() {executor.spin();});

  const bool service_ready = client->wait_for_service(2s);
  EXPECT_TRUE(service_ready);
  {
    std::unique_lock<std::mutex> lock(state_mutex);
    const bool initial_state_received =
      state_changed.wait_for(lock, 2s, [&]() {return state_received;});
    EXPECT_TRUE(initial_state_received);
    if (initial_state_received) {
      EXPECT_TRUE(latest_state);
    }
    state_received = false;
  }

  if (service_ready) {
    auto request = std::make_shared<std_srvs::srv::SetBool::Request>();
    request->data = false;
    auto response = client->async_send_request(request);
    const bool response_ready =
      response.wait_for(2s) == std::future_status::ready;
    EXPECT_TRUE(response_ready);
    if (response_ready) {
      EXPECT_TRUE(response.get()->success);
    }

    {
      std::unique_lock<std::mutex> lock(state_mutex);
      const bool released_state_received =
        state_changed.wait_for(lock, 2s, [&]() {return state_received;});
      EXPECT_TRUE(released_state_received);
      if (released_state_received) {
        EXPECT_FALSE(latest_state);
      }
    }
  }

  executor.cancel();
  spin_thread.join();
  (void)subscription;
}

TEST_F(RosContextFixture, AllowsExplicitDevelopmentStartupOverride)
{
  rclcpp::NodeOptions options;
  options.parameter_overrides({rclcpp::Parameter("initial_drivestop", false)});
  auto whs = std::make_shared<kanga_whs::WhsNode>("whs_override_test", options);
  EXPECT_FALSE(whs->get_parameter("initial_drivestop").as_bool());
}

}  // namespace
