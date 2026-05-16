execute_process(COMMAND "/home/jetson/software/world_canvas/build/world_canvas_tools/rqt_annotation_data/catkin_generated/python_distutils_install.sh" RESULT_VARIABLE res)

if(NOT res EQUAL 0)
  message(FATAL_ERROR "execute_process(/home/jetson/software/world_canvas/build/world_canvas_tools/rqt_annotation_data/catkin_generated/python_distutils_install.sh) returned error code ")
endif()
