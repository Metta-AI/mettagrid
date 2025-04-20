from mettagrid.action_handler cimport ActionArg
from mettagrid.grid cimport Grid
from mettagrid.grid_object cimport GridObjectId

cdef class ActionHandler:
    def __init__(self, string action_name):
        self._action_name = action_name
        self._priority = 0

        self._stats.success = "action." + action_name
        self._stats.failure = "action." + action_name + ".failed"
        self._stats.first_use = "action." + action_name + ".first_use"

        for t, n in enumerate(ObjectTypeNames):
            self._stats.target[t] = self._stats.success + "." + n
            self._stats.target_first_use[t] = self._stats.first_use + "." + n

    cdef void init(self, Grid *grid):
        self._grid = grid

    cdef bint handle_action(
        self,
        unsigned int actor_id,
        GridObjectId actor_object_id,
        ActionArg arg,
        unsigned int current_timestep):
        return False

    cdef unsigned char max_arg(self):
        return 0

    cpdef string action_name(self):
        return self._action_name
