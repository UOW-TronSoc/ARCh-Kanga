cmake_minimum_required(VERSION 3.8)
project(kanga_core_drive)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(std_srvs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(custom_odrive REQUIRED)

include_directories(include)

add_executable(drive_manager
  src/drive_manager.cpp
  src/drive_manager_main.cpp
)
ament_target_dependencies(drive_manager
  rclcpp
  std_srvs
  custom_odrive
)
target_compile_features(drive_manager PRIVATE cxx_std_17)

add_executable(wheel_joint_state_publisher
  src/wheel_joint_state_publisher.cpp
  src/wheel_joint_state_publisher_main.cpp
)
ament_target_dependencies(wheel_joint_state_publisher
  rclcpp
  sensor_msgs
  custom_odrive
)
target_compile_features(wheel_joint_state_publisher PRIVATE cxx_std_17)

install(TARGETS
  drive_manager
  wheel_joint_state_publisher
  DESTINATION lib/${PROJECT_NAME}
)

# Fibre commissioning stays Python (wraps custom_odrive commission).
install(PROGRAMS
  scripts/commission_wheels.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME commission_wheels
)
install(FILES
  scripts/config_merge.py
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY config launch
  DESTINATION share/${PROJECT_NAME}
)

install(FILES README.md
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_config_merge test/test_config_merge.py)
endif()

ament_package()
