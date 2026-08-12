cmake_minimum_required(VERSION 3.8)
project(kanga_core_description)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

ament_python_install_package(${PROJECT_NAME})

install(DIRECTORY config launch meshes rviz urdf
  DESTINATION share/${PROJECT_NAME}
)

install(FILES README.md
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(
    test_core_2026_description
    test/test_core_2026_description.py
  )
  ament_add_pytest_test(test_drivetrain_profile test/test_drivetrain_profile.py)
endif()

ament_package()
