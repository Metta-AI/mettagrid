from libcpp.vector cimport vector
from libcpp.string cimport string
from mettagrid.observation_encoder cimport ObsType
from .constants cimport InventoryItem, InventoryItemNames
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

    inline void update_inventory(InventoryItem item, short amount, float *reward):
        this.inventory[<InventoryItem>item] += amount
        if reward is not NULL and amount > 0:
            reward[0] += amount * this.resource_reward

        if this.inventory[<InventoryItem>item] > this.max_items:
            this.inventory[<InventoryItem>item] = this.max_items

    inline short update_energy(short amount, float *reward):
        if amount < 0:
            amount = max(-this.energy, amount)
        else:
            amount = min(this.max_energy - this.energy, amount)

        this.energy += amount
        if reward is not NULL and amount > 0:
            reward[0] += amount * this.energy_reward

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
    vector[string] feature_names():
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