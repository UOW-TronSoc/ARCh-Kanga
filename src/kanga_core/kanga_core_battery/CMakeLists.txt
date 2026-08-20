cmake_minimum_required(VERSION 3.8)
project(kanga_core_battery)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(can_msgs REQUIRED)
find_package(kanga_interfaces REQUIRED)

add_executable(bms_can_node
  src/bms_can_node.cpp
  src/main.cpp
)

target_compile_features(bms_can_node PRIVATE cxx_std_17)

target_include_directories(bms_can_node PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

ament_target_dependencies(bms_can_node
  rclcpp
  can_msgs
  kanga_interfaces
)

install(TARGETS bms_can_node
  RUNTIME DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY include/
  DESTINATION include
)

install(DIRECTORY launch
  DESTINATION share/${PROJECT_NAME}
)

install(FILES README.md
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
