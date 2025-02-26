
from omegaconf import OmegaConf

from mettagrid.grid_object cimport GridLocation, Orientation
from mettagrid.action cimport ActionArg
from mettagrid.objects.agent cimport Agent
from mettagrid.objects.metta_object cimport MettaObject
from mettagrid.objects.constants cimport ObjectType, Events, GridLayer, Obje    ctTypeNames, InventoryItem
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
        if target == NULL or not (target._type_id == ObjectType.GenericConverterT or target._type_id == ObjectType.MineT or target._type_id == ObjectType.GeneratorT or target._type_id == ObjectType.AltarT or target._type_id == ObjectType.ArmoryT or target._type_id == ObjectType.LaseryT or target._type_id == ObjectType.LabT or target._type_id == ObjectType.FactoryT or target._type_id == ObjectType.TempleT):
            return False

        cdef Converter *converter = <Converter*> target

        for i in range(converter.inventory.size()):
            actor.update_inventory(<InventoryItem>i, converter.inventory[i], &self.env._rewards[actor_id])
            converter.inventory[i] = 0
        
        if converter.maybe_start_converting():
            self.env._event_manager.schedule_event(Events.FinishConverting, converter.recipe_duration, converter.id, 0)

        return True
