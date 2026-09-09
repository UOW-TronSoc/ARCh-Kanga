cmake_minimum_required(VERSION 3.8)
project(kanga_core_bringup)

find_package(ament_cmake REQUIRED)

install(DIRECTORY launch
  DESTINATION share/${PROJECT_NAME}
)

install(FILES README.md
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(
    test_rover_launch_contract
    test/test_rover_launch_contract.py
  )
endif()

ament_package()
