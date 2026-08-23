cmake_minimum_required(VERSION 3.8)
project(kanga_core_simulation)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(ignition-gazebo6 REQUIRED)
find_package(ignition-plugin1 REQUIRED COMPONENTS register)
find_package(kanga_core_microcontroller REQUIRED)
find_package(kanga_interfaces REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(std_srvs REQUIRED)

set(IGN_PLUGIN_VER ${ignition-plugin1_VERSION_MAJOR})

add_library(kanga_core_simulation_support SHARED
  src/drive_simulation.cpp
  src/passive_constraint.cpp
)
target_include_directories(kanga_core_simulation_support PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
ament_target_dependencies(kanga_core_simulation_support
  kanga_core_microcontroller
)
target_compile_features(kanga_core_simulation_support PUBLIC cxx_std_17)

add_library(kanga_core_hardware_system SHARED
  src/core_hardware_system.cpp
)
target_link_libraries(kanga_core_hardware_system
  kanga_core_simulation_support
  ignition-plugin${IGN_PLUGIN_VER}::ignition-plugin${IGN_PLUGIN_VER}
  ignition-gazebo6::ignition-gazebo6
)
ament_target_dependencies(kanga_core_hardware_system
  builtin_interfaces
  geometry_msgs
  kanga_interfaces
  nav_msgs
  rclcpp
  sensor_msgs
  std_msgs
  std_srvs
)
target_compile_features(kanga_core_hardware_system PRIVATE cxx_std_17)

add_library(kanga_passive_suspension_system SHARED
  src/passive_suspension_system.cpp
)
target_link_libraries(kanga_passive_suspension_system
  kanga_core_simulation_support
  ignition-plugin${IGN_PLUGIN_VER}::ignition-plugin${IGN_PLUGIN_VER}
  ignition-gazebo6::ignition-gazebo6
)
target_compile_features(kanga_passive_suspension_system PRIVATE cxx_std_17)

install(TARGETS
  kanga_core_simulation_support
  kanga_core_hardware_system
  kanga_passive_suspension_system
  EXPORT export_kanga_core_simulation
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION lib/${PROJECT_NAME}
)
install(DIRECTORY include/
  DESTINATION include
)
install(DIRECTORY config urdf
  DESTINATION share/${PROJECT_NAME}
)

install(FILES README.md
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_gtest(test_drive_simulation test/test_drive_simulation.cpp)
  target_link_libraries(test_drive_simulation kanga_core_simulation_support)
  target_compile_features(test_drive_simulation PRIVATE cxx_std_17)

  ament_add_gtest(test_passive_constraint test/test_passive_constraint.cpp)
  target_link_libraries(test_passive_constraint kanga_core_simulation_support)
  target_compile_features(test_passive_constraint PRIVATE cxx_std_17)

  ament_add_pytest_test(
    test_simulation_description
    test/test_simulation_description.py
  )
endif()

ament_export_targets(export_kanga_core_simulation HAS_LIBRARY_TARGET)
ament_export_include_directories(include)
ament_export_dependencies(kanga_core_microcontroller)

ament_package()
