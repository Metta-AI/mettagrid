from libcpp.string cimport string
from libcpp.map cimport map
from libcpp.vector cimport vector

from mettagrid.grid_object cimport TypeId, GridObjectId
from mettagrid.grid cimport Grid

ctypedef unsigned int ActionArg

cdef extern from "action_handler.hpp":
    cdef cppclass StatNames:
        string success
        string first_use
        string failure

        map[TypeId, string] target
        map[TypeId, string] target_first_use
        vector[string] group

    cdef cppclass ActionHandler:
        unsigned char priority
        ActionHandler(string action_name)
        void init(Grid* grid)
        bint handle_action(
            unsigned int actor_id,
            GridObjectId actor_object_id,
            ActionArg arg,
            unsigned int current_timestep)
        unsigned char max_arg()
        string action_name()

