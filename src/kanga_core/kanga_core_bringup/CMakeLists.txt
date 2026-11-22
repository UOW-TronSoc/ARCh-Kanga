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
  find_package(launch_testing_ament_cmake REQUIRED)
  ament_add_pytest_test(
    test_rover_launch_contract
    test/test_rover_launch_contract.py
  )
  add_launch_test(test/test_controller_launch_parameters.py TIMEOUT 60)
  add_launch_test(test/test_core_parameter_loading.py TIMEOUT 90)
endif()

ament_package()
