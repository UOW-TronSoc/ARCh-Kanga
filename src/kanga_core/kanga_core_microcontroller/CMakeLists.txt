cmake_minimum_required(VERSION 3.8)
project(kanga_core_microcontroller)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(tf2_ros REQUIRED)

add_library(suspension_kinematics src/suspension_kinematics.cpp)
target_include_directories(suspension_kinematics PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
target_compile_features(suspension_kinematics PUBLIC cxx_std_17)

add_executable(suspension_joint_state_publisher
  src/suspension_joint_state_publisher.cpp
)
target_link_libraries(suspension_joint_state_publisher suspension_kinematics)
ament_target_dependencies(suspension_joint_state_publisher
  rclcpp
  sensor_msgs
  std_msgs
)
target_compile_features(suspension_joint_state_publisher PRIVATE cxx_std_17)

add_executable(body_pose_tf_broadcaster
  src/body_pose_tf_broadcaster.cpp
)
ament_target_dependencies(body_pose_tf_broadcaster
  geometry_msgs
  rclcpp
  tf2_ros
)
target_compile_features(body_pose_tf_broadcaster PRIVATE cxx_std_17)

install(TARGETS
  suspension_kinematics
  suspension_joint_state_publisher
  body_pose_tf_broadcaster
  EXPORT export_suspension_kinematics
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
  ament_add_gtest(test_suspension_kinematics test/test_suspension_kinematics.cpp)
  target_link_libraries(test_suspension_kinematics suspension_kinematics)
  target_compile_features(test_suspension_kinematics PRIVATE cxx_std_17)

endif()

ament_export_targets(export_suspension_kinematics HAS_LIBRARY_TARGET)
ament_export_include_directories(include)

ament_package()
