from mettagrid.cpp_action_handler cimport CppActionHandler
from mettagrid.cpp_grid_object cimport cpp_GridObjectId
from libcpp.string cimport string
from mettagrid.cpp_grid cimport CppGrid

cdef class ActionHandler:
    cdef CppActionHandler* _impl
    # Add this line to declare the _init_grid method
    cdef void _init_grid(self, CppGrid* grid)
    cpdef bint handle_action(self, unsigned int actor_id, cpp_GridObjectId actor_object_id, unsigned int arg, unsigned int timestep)
    cpdef unsigned char max_arg(self)
    cpdef str action_name(self)