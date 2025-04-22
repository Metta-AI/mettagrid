from libcpp.string cimport string
from libcpp.map cimport map as cpp_map
from mettagrid.cpp_action_handler cimport CppDefaultActionHandler, cpp_ActionConfig
from mettagrid.cpp_grid cimport CppGrid
from mettagrid.cpp_grid_object cimport cpp_GridObjectId
from mettagrid.grid cimport Grid

cdef class ActionHandler:
    def __cinit__(self, dict cfg=None, str action_name=""):
        cdef cpp_ActionConfig cpp_cfg
        if cfg is not None:
            for k, v in cfg.items():
                cpp_cfg[k.encode()] = v
        self._impl = new CppDefaultActionHandler(cpp_cfg, action_name.encode())

    def __dealloc__(self):
        del self._impl

    # Add this public method
    def init(self, grid:Grid):
        """
        Initialize the action handler with a grid.
        
        Args:
            grid: The Grid object to use for this action handler
        """
        self._init_grid(grid._impl)

    # Keep your existing private method
    cdef void _init_grid(self, CppGrid *grid):
        self._impl.cpp_init(grid)

    cpdef bint handle_action(self, unsigned int actor_id, cpp_GridObjectId actor_object_id, unsigned int arg, unsigned int timestep):
        return self._impl.cpp_handle_action(actor_id, actor_object_id, arg, timestep)

    cpdef unsigned char max_arg(self):
        return self._impl.cpp_max_arg()

    cpdef str action_name(self):
        cdef object result = self._impl.cpp_action_name()
        if isinstance(result, bytes):
            return result.decode()
        return result
