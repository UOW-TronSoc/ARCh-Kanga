cmake_minimum_required(VERSION 3.8)
project(kanga_joy)

find_package(ament_cmake REQUIRED)

install(PROGRAMS
  scripts/bench_teleop.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME bench_teleop
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

ament_package()
