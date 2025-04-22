# cpp_action_handler.pxd
from libcpp.string cimport string
from libcpp.map cimport map
from libcpp.vector cimport vector
from libcpp cimport bool

from mettagrid.cpp_grid_object cimport cpp_TypeId, cpp_GridObjectId
from mettagrid.grid cimport CppGrid

ctypedef unsigned int cpp_ActionArg
ctypedef map[string, int] cpp_ActionConfig

cdef extern from "cpp_action_handler.hpp":
    cdef cppclass CppStatNames:
        string success
        string first_use
        string failure

        map[cpp_TypeId, string] target
        map[cpp_TypeId, string] target_first_use
        vector[string] group

    cdef cppclass CppActionHandler:
        unsigned char priority

        CppActionHandler(const cpp_ActionConfig& cfg, const string& action_name)
        void cpp_init(CppGrid* grid)
        bool cpp_handle_action(
            unsigned int actor_id,
            cpp_GridObjectId actor_object_id,
            cpp_ActionArg arg,
            unsigned int current_timestep)
        unsigned char cpp_max_arg() const
        string cpp_action_name() const

    cdef cppclass CppDefaultActionHandler(CppActionHandler):
        CppDefaultActionHandler(cpp_ActionConfig&, string) except +