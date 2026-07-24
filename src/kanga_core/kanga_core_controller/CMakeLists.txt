cmake_minimum_required(VERSION 3.8)
project(kanga_core_controller)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(custom_odrive REQUIRED)

include_directories(include)

# Pure kinematics (no ROS) — unit-tested offline.
add_library(kanga_kinematics src/kinematics.cpp)
target_include_directories(kanga_kinematics PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
target_compile_features(kanga_kinematics PUBLIC cxx_std_17)

add_executable(wheel_command_mapper
  src/wheel_command_mapper.cpp
  src/wheel_command_mapper_main.cpp
)
ament_target_dependencies(wheel_command_mapper
  rclcpp
  geometry_msgs
  std_msgs
  custom_odrive
)
target_link_libraries(wheel_command_mapper kanga_kinematics)
target_compile_features(wheel_command_mapper PRIVATE cxx_std_17)

install(TARGETS
  kanga_kinematics
  wheel_command_mapper
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY include/
  DESTINATION include
)

install(DIRECTORY config launch
  DESTINATION share/${PROJECT_NAME}
)

install(FILES README.md
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(test_kinematics test/test_kinematics.cpp)
  target_link_libraries(test_kinematics kanga_kinematics)
endif()

ament_package()
