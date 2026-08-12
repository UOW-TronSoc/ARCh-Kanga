cmake_minimum_required(VERSION 3.8)
project(kanga_sim)

find_package(ament_cmake REQUIRED)

install(DIRECTORY launch worlds
  DESTINATION share/${PROJECT_NAME}
)

install(PROGRAMS scripts/core_simulation_contract_check.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME core_simulation_contract_check
)

install(FILES README.md
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(launch_testing_ament_cmake REQUIRED)
  add_launch_test(test/test_core_simulation_launch.py TIMEOUT 60)
endif()

ament_package()
