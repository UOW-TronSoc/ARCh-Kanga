cmake_minimum_required(VERSION 3.8)
project(kanga_launch_agent)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

ament_python_install_package(${PROJECT_NAME})

install(PROGRAMS
  scripts/launch_agent
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY launch deploy
  DESTINATION share/${PROJECT_NAME}
)

install(FILES README.md
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_manager
    test/test_manager.py
    TIMEOUT 30
  )
endif()

ament_package()
