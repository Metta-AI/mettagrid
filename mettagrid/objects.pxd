# distutils: language=c++
# cython: warn.undeclared=False
# cython: c_api_binop_methods=True

from libcpp.vector cimport vector
from libcpp.map cimport map
from libcpp.string cimport string
from mettagrid.grid_env import StatsTracker
from libc.stdio cimport printf
from mettagrid.observation_encoder cimport ObservationEncoder, ObsType
from mettagrid.grid_object cimport GridObject, TypeId, GridCoord, GridLocation, GridObjectId
from mettagrid.event cimport EventHandler, EventArg

cdef enum GridLayer:
    Agent_Layer = 0
    Object_Layer = 1

ctypedef map[string, int] ObjectConfig

cdef cppclass MettaObject(GridObject):
    unsigned int hp

    inline void init_mo(ObjectConfig cfg):
        this.hp = cfg[b"hp"]

    inline bint usable(const Agent *actor):
        return False

cdef cppclass Usable(MettaObject):
    unsigned int use_cost
    unsigned int cooldown
    unsigned char ready

    inline void init_usable(ObjectConfig cfg):
        this.use_cost = cfg[b"use_cost"]
        this.cooldown = cfg[b"cooldown"]
        this.ready = 1

    inline bint usable(const Agent *actor):
        return this.ready and this.use_cost <= actor.energy

cdef enum ObjectType:
    AgentT = 0
    WallT = 1
    GeneratorT = 2
    ConverterT = 3
    AltarT = 4
    Count = 5

cdef vector[string] ObjectTypeNames # defined in objects.pyx

cdef enum InventoryItem:
    r1 = 0,
    r2 = 1,
    r3 = 2,
    InventoryCount = 3

cdef vector[string] InventoryItemNames # defined in objects.pyx


cdef cppclass Agent(MettaObject):
    unsigned char frozen
    unsigned char freeze_duration
    unsigned char energy
    unsigned char orientation
    unsigned char shield
    unsigned char shield_upkeep
    vector[unsigned char] inventory
    unsigned char max_items
    unsigned char max_energy
    float energy_reward

    inline Agent(GridCoord r, GridCoord c, ObjectConfig cfg):
        GridObject.init(ObjectType.AgentT, GridLocation(r, c, GridLayer.Agent_Layer))
        MettaObject.init_mo(cfg)
        this.frozen = 0
        this.freeze_duration = cfg[b"freeze_duration"]
        this.max_energy = cfg[b"max_energy"]
        this.energy = 0
        this.update_energy(cfg[b"initial_energy"], NULL)
        this.shield_upkeep = cfg[b"upkeep.shield"]
        this.orientation = 0
        this.inventory.resize(InventoryItem.InventoryCount)
        this.max_items = cfg[b"max_inventory"]
        this.energy_reward = float(cfg[b"energy_reward"]) / 1000.0
        this.shield = False

    inline void update_inventory(InventoryItem item, short amount):
        this.inventory[<InventoryItem>item] += amount
        if this.inventory[<InventoryItem>item] > this.max_items:
            this.inventory[<InventoryItem>item] = this.max_items

    inline short update_energy(short amount, float *reward):
        if amount < 0:
            amount = max(-this.energy, amount)
        else:
            amount = min(this.max_energy - this.energy, amount)

        this.energy += amount
        if reward is not NULL:
            reward[0] += amount * this.energy_reward

        return amount

    inline void obs(ObsType[:] obs):
        # #ObservationDefinition
        obs[0] = 1
        obs[1] = this.hp
        obs[2] = this.frozen
        obs[3] = this.energy
        obs[4] = this.orientation
        obs[5] = this.shield

        cdef unsigned short idx = 6
        cdef unsigned short i
        for i in range(InventoryItem.InventoryCount):
            obs[idx + i] = this.inventory[i]

    @staticmethod
    inline vector[string] feature_names():
        return [
            "agent", "agent:hp", "agent:frozen", "agent:energy", "agent:orientation",
            "agent:shield"
        ] + [
            "agent:inv:" + n for n in InventoryItemNames]

cdef cppclass Wall(MettaObject):
    inline Wall(GridCoord r, GridCoord c, ObjectConfig cfg):
        GridObject.init(ObjectType.WallT, GridLocation(r, c, GridLayer.Object_Layer))
        MettaObject.init_mo(cfg)

    inline void obs(ObsType[:] obs):
        # #ObservationDefinition
        obs[0] = 1
        obs[1] = hp

    @staticmethod
    inline vector[string] feature_names():
        return ["wall", "wall:hp"]

cdef cppclass Generator(Usable):
    unsigned int r1

    inline Generator(GridCoord r, GridCoord c, ObjectConfig cfg):
        GridObject.init(ObjectType.GeneratorT, GridLocation(r, c, GridLayer.Object_Layer))
        MettaObject.init_mo(cfg)
        Usable.init_usable(cfg)
        this.r1 = cfg[b"initial_resources"]

    inline bint usable(const Agent *actor):
        return Usable.usable(actor) and this.r1 > 0

    inline void obs(ObsType[:] obs):
        # #ObservationDefinition
        obs[0] = 1
        obs[1] = this.hp
        obs[2] = this.r1
        obs[3] = this.ready and this.r1 > 0

    @staticmethod
    inline vector[string] feature_names():
        return ["generator", "generator:hp", "generator:r1", "generator:ready"]

cdef cppclass ConverterRecipe:
    # positive for gain, negative for loss
    vector[char] delta_resources
    short delta_energy
    short reward

    inline ConverterRecipe():
        this.delta_resources.resize(InventoryItem.InventoryCount)
        this.delta_resources[InventoryItem.r1] = -1
        this.delta_resources[InventoryItem.r2] = 1
        this.delta_energy = 100
        this.reward = 0

cdef cppclass Converter(Usable):
    vector[ConverterRecipe] recipes

    inline Converter(GridCoord r, GridCoord c, ObjectConfig cfg, vector[ConverterRecipe] recipes):
        GridObject.init(ObjectType.ConverterT, GridLocation(r, c, GridLayer.Object_Layer))
        MettaObject.init_mo(cfg)
        Usable.init_usable(cfg)
        this.recipes = recipes

    inline bint usable(const Agent *actor):
        cdef ConverterRecipe recipe = this.recipes[0]
        if -recipe.delta_energy > actor.energy:
            return False
        for i in range(InventoryItem.InventoryCount):
            if -recipe.delta_resources[i] > actor.inventory[i]:
                return False
        return Usable.usable(actor)

    inline obs(ObsType[:] obs):
        # #ObservationDefinition
        obs[0] = 1
        obs[1] = hp
        obs[2] = ready

    @staticmethod
    inline vector[string] feature_names():
        return ["converter", "converter:hp", "converter:ready"]

cdef cppclass Altar(Usable):
    inline Altar(GridCoord r, GridCoord c, ObjectConfig cfg):
        GridObject.init(ObjectType.AltarT, GridLocation(r, c, GridLayer.Object_Layer))
        MettaObject.init_mo(cfg)
        Usable.init_usable(cfg)

    inline void obs(ObsType[:] obs):
        # #ObservationDefinition
        obs[0] = 1
        obs[1] = hp
        obs[2] = ready

    @staticmethod
    inline vector[string] feature_names():
        return ["altar", "altar:hp", "altar:ready"]

cdef map[TypeId, GridLayer] ObjectLayers

cdef class ResetHandler(EventHandler):
    cdef inline void handle_event(self, GridObjectId obj_id, EventArg arg):
        cdef Usable *usable = <Usable*>self.env._grid.object(obj_id)
        if usable is NULL:
            return

        usable.ready = True
        self.env._stats.game_incr("resets." + ObjectTypeNames[usable._type_id])

cdef enum Events:
    Reset = 0
