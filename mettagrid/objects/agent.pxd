from libcpp.vector cimport vector
from libcpp.string cimport string
from mettagrid.observation_encoder cimport ObsType
from mettagrid.grid_object cimport GridCoord, GridLocation, GridObject
from .constants cimport ObjectType, GridLayer, InventoryItem
from .metta_object cimport MettaObject, ObjectConfig

cdef cppclass Agent(MettaObject):
    unsigned char group
    unsigned char frozen
    unsigned char attack_damage
    unsigned char freeze_duration
    unsigned char energy
    unsigned char orientation
    unsigned char shield
    unsigned char shield_upkeep
    vector[unsigned char] inventory
    unsigned char max_items
    unsigned char max_energy
    float energy_reward
    float resource_reward
    float freeze_reward
    string group_name
    unsigned char color

    inline Agent(
        GridCoord r, GridCoord c,
        string group_name,
        unsigned char group_id,
        ObjectConfig cfg):
        GridObject.init(ObjectType.AgentT, GridLocation(r, c, GridLayer.Agent_Layer))
        MettaObject.init_mo(cfg)

        this.group_name = group_name
        this.group = group_id
        this.frozen = 0
        this.attack_damage = cfg[b"attack_damage"]
        this.freeze_duration = cfg[b"freeze_duration"]
        this.max_energy = cfg[b"max_energy"]
        this.energy = 0
        this.update_energy(cfg[b"initial_energy"], NULL)
        this.shield_upkeep = cfg[b"upkeep.shield"]
        this.orientation = 0
        this.inventory.resize(InventoryItem.InventoryCount)
        this.max_items = cfg[b"max_inventory"]
        this.energy_reward = float(cfg[b"energy_reward"]) / 1000.0
        this.resource_reward = float(cfg[b"resource_reward"]) / 1000.0
        this.freeze_reward = float(cfg[b"freeze_reward"]) / 1000.0
        this.shield = False
        this.color = 0

    void update_inventory(InventoryItem item, short amount, float *reward)

    short update_energy(short amount, float *reward)

    void obs(ObsType[:] obs)

    @staticmethod
    vector[string] feature_names()