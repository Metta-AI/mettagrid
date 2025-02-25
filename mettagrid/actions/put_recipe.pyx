
from omegaconf import OmegaConf

from mettagrid.grid_object cimport GridLocation, Orientation
from mettagrid.action cimport ActionArg
from mettagrid.objects.agent cimport Agent
from mettagrid.objects.metta_object cimport MettaObject
from mettagrid.objects.constants cimport ObjectType, Events, GridLayer, ObjectTypeNames, InventoryItem
from mettagrid.objects.converter cimport Converter
from mettagrid.actions.actions cimport MettaActionHandler

# Puts one recipe worth of resources into a Converter. Noop if not enough resources.
cdef class PutRecipe(MettaActionHandler):
    def __init__(self, cfg: OmegaConf):
        MettaActionHandler.__init__(self, cfg, "put_recipe")

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
        # xcxc needs to be any converter
        if target == NULL or not target._type_id == ObjectType.GenericConverterT:
            return False

        cdef Converter *converter = <Converter*> target

        for i in range(converter.recipe_input.size()):
            if converter.recipe_input[i] > actor.inventory[i]:
                return False

        # xcxc add stats
        for i in range(converter.recipe_input.size()):
            converter.input_inventory[i] += converter.recipe_input[i]
            actor.update_inventory(<InventoryItem>i, -converter.recipe_input[i], &self.env._rewards[actor_id])

        if converter.maybe_start_converting():
            self.env._event_manager.schedule_event(Events.FinishConverting, converter.recipe_duration, converter.id, 0)

        return True
