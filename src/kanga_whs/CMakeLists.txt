cmake_minimum_required(VERSION 3.8)
project(kanga_whs)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(std_srvs REQUIRED)

add_executable(whs_node
  src/whs_node.cpp
  src/main.cpp
)

target_compile_features(whs_node PRIVATE cxx_std_17)

target_include_directories(whs_node PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

ament_target_dependencies(whs_node
  rclcpp
  std_msgs
  std_srvs
)

install(TARGETS whs_node
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

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)

  ament_add_gtest(test_whs_node
    test/test_whs_node.cpp
    src/whs_node.cpp
  )
  target_compile_features(test_whs_node PRIVATE cxx_std_17)
  target_include_directories(test_whs_node PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
  )
  ament_target_dependencies(test_whs_node
    rclcpp
    std_msgs
    std_srvs
  )
endif()

ament_package()
