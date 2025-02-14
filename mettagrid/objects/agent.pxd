from libcpp.vector cimport vector
from libcpp.string cimport string
from mettagrid.observation_encoder cimport ObsType
from mettagrid.grid_object cimport GridCoord, GridLocation, GridObject
from mettagrid.stats_tracker cimport StatsTracker
from .constants cimport ObjectType, GridLayer, InventoryItem, InventoryItemNames
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
    unsigned char agent_id
    StatsTracker stats

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

    inline void update_inventory(InventoryItem item, short amount, float *reward):
        this.inventory[<InventoryItem>item] += amount
        if reward is not NULL and amount > 0:
            reward[0] += amount * this.resource_reward

        if this.inventory[<InventoryItem>item] > this.max_items:
            this.inventory[<InventoryItem>item] = this.max_items

        if amount > 0:
            this.stats.add(InventoryItemNames[item], b"gained", amount)
            this.stats.add(InventoryItemNames[item], b"gained", this.group_name, amount)
        else:
            this.stats.add(InventoryItemNames[item], b"lost", -amount)
            this.stats.add(InventoryItemNames[item], b"lost", this.group_name, -amount)


    inline short update_energy(short amount, float *reward):
        if amount < 0:
            amount = max(-this.energy, amount)
        else:
            amount = min(this.max_energy - this.energy, amount)

        this.energy += amount
        if reward is not NULL and amount > 0:
            reward[0] += amount * this.energy_reward

        this.stats.add(b"energy.gained", amount)
        this.stats.add(b"energy.gained", this.group_name, amount)

        return amount

    inline void obs(ObsType[:] obs):
        obs[0] = 1
        obs[1] = this.group
        obs[2] = this.hp
        obs[3] = this.frozen
        obs[4] = this.energy
        obs[5] = this.orientation
        obs[6] = this.shield
        obs[7] = this.color
        cdef unsigned short idx = 8

        cdef unsigned short i
        for i in range(InventoryItem.InventoryCount):
            obs[idx + i] = this.inventory[i]

    @staticmethod
    inline vector[string] feature_names():
        return [
            "agent",
            "agent:group",
            "agent:hp",
            "agent:frozen",
            "agent:energy",
            "agent:orientation",
            "agent:shield",
            "agent:color"
        ] + [
            "agent:inv:" + n for n in InventoryItemNames]