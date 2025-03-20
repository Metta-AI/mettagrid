
from libc.stdio cimport printf

from omegaconf import OmegaConf

from mettagrid.grid_object cimport GridLocation, Orientation
from mettagrid.action cimport ActionArg
from mettagrid.objects.agent cimport Agent
from mettagrid.grid_object cimport GridLocation, GridObjectId, Orientation, GridObject
from mettagrid.action cimport ActionHandler, ActionArg
from mettagrid.actions.actions cimport MettaActionHandler
from mettagrid.objects.metta_object cimport MettaObject
from mettagrid.objects.constants cimport GridLayer

cdef class Swap(MettaActionHandler):
    def __init__(self, cfg: OmegaConf):
        MettaActionHandler.__init__(self, cfg, "swap")

    cdef unsigned char max_arg(self):
        return 0

    cdef bint _handle_action(
        self,
        unsigned int actor_id,
        Agent * actor,
        ActionArg arg):

        cdef GridLocation target_loc = self.env._grid.relative_location(
            actor.location,
            <Orientation>actor.orientation
        )
        cdef MettaObject *target
        target = <MettaObject*>self.env._grid.object_at(target_loc)
        if target == NULL:
            target_loc.layer = GridLayer.Object_Layer
            target = <MettaObject*>self.env._grid.object_at(target_loc)
        if target == NULL:
            return False

        if not target.swappable():
            return False

        self.env._grid.swap_objects(actor.id, target.id)
        return True
