cmake_minimum_required(VERSION 3.8)
project(kanga_joy)

find_package(ament_cmake REQUIRED)

install(PROGRAMS
  scripts/bench_teleop.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME bench_teleop
)

install(PROGRAMS
  scripts/keyboard_joy.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME keyboard_joy
)

install(PROGRAMS
  scripts/keyboard_bench_teleop.bash
  DESTINATION lib/${PROJECT_NAME}
  RENAME keyboard_bench_teleop
)

install(PROGRAMS
  scripts/controller_test.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME controller_test
)

install(DIRECTORY config launch
  DESTINATION share/${PROJECT_NAME}
)

install(FILES README.md
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_bench_teleop
    test/test_bench_teleop.py
    TIMEOUT 30
  )
endif()

ament_package()
