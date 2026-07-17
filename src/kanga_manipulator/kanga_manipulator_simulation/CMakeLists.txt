cmake_minimum_required(VERSION 3.8)
project(kanga_manipulator_simulation)

find_package(ament_cmake REQUIRED)

install(FILES README.md
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
