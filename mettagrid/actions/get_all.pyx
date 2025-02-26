
from omegaconf import OmegaConf

from mettagrid.grid_object cimport GridLocation, Orientation
from mettagrid.action cimport ActionArg
from mettagrid.objects.agent cimport Agent
from mettagrid.objects.metta_object cimport MettaObject
from mettagrid.objects.constants cimport ObjectType, Events, GridLayer, InventoryItem
from mettagrid.objects.converter cimport Converter
from mettagrid.actions.actions cimport MettaActionHandler

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
        if target == NULL or not target.has_inventory():
            return False

        # ##Converter_and_HasInventory_are_the_same_thing
        # It's more correct to cast this as a HasInventory, but right now Converters are
        # the only implementors of HasInventory, and we also need to call maybe_start_converting
        # on them. We should later refactor this to we call .update_inventory on the target, and
        # have this automatically call maybe_start_converting. That's hard because we need to
        # let it maybe schedule events.
        cdef Converter *converter = <Converter*> target
        if not converter.inventory_is_accessible():
            return False

        for i in range(target_with_inventory.inventory.size()):
            # The actor will destroy anything it can't hold. That's not intentional, so feel free
            # to fix it.
            actor.update_inventory(<InventoryItem>i, target_with_inventory.inventory[i], &self.env._rewards[actor_id])
            target_with_inventory.inventory[i] = 0
        
        if converter.maybe_start_converting():
            self.env._event_manager.schedule_event(Events.FinishConverting, converter.recipe_duration, converter.id, 0)

        return True
