
from omegaconf import OmegaConf

from mettagrid.grid_object cimport GridLocation, Orientation
from mettagrid.action cimport ActionArg
from mettagrid.objects.agent cimport Agent
from mettagrid.objects.metta_object cimport MettaObject
from mettagrid.objects.constants cimport ObjectType, Events, GridLayer, ObjectTypeNames, InventoryItem
from mettagrid.objects.converter cimport Converter
from mettagrid.actions.actions cimport MettaActionHandler

# For now, use will both put and get.
cdef class GetAll(MettaActionHandler):
    def __init__(self, cfg: OmegaConf):
        MettaActionHandler.__init__(self, cfg, "get_all")

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
        target_loc.layer = GridLayer.Object_Layer
        cdef MettaObject *target = <MettaObject*>self.env._grid.object_at(target_loc)
        if target == NULL or not target._type_id == ObjectType.GenericConverterT:
            return False

        cdef Converter *converter = <Converter*> target

        for i in range(converter.output_inventory.size()):
            actor.update_inventory(<InventoryItem>i, converter.output_inventory[i], &self.env._rewards[actor_id])
            converter.output_inventory[i] = 0
        
        if converter.maybe_start_converting():
            self.env._event_manager.schedule_event(Events.FinishConverting, converter.recipe_duration, converter.id, 0)

        return True
