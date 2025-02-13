from libc.string cimport strcat, strcpy
from mettagrid.grid_env cimport StatsTracker
from mettagrid.observation_encoder cimport ObsType
from .constants cimport InventoryItem, InventoryItemNames
from .agent cimport Agent
from .usable cimport Usable

cdef cppclass Converter(Usable):
    short prey_r1_output_energy;
    short predator_r1_output_energy;
    short predator_r2_output_energy;

    bint usable(const Agent *actor):
        return Usable.usable(actor) and (
            actor.inventory[InventoryItem.r1] > 0 or
            (actor.inventory[InventoryItem.r2] > 0 and
            actor.group_name == b"predator")
        )

    void use(Agent *actor, unsigned int actor_id, StatsTracker stats, float *rewards):
        cdef unsigned int energy_gain = 0
        cdef InventoryItem consumed_resource = InventoryItem.r1
        cdef InventoryItem produced_resource = InventoryItem.r2
        cdef char stat_name[256]
        cdef unsigned int potential_energy_gain = this.prey_r1_output_energy
        if actor.group_name == b"predator":
            if actor.inventory[InventoryItem.r2] > 0:
                # eat meat if you can
                consumed_resource = InventoryItem.r2
                produced_resource = InventoryItem.r3
                potential_energy_gain = this.predator_r2_output_energy
            else:
                potential_energy_gain = this.predator_r1_output_energy
                produced_resource = InventoryItem.r3

        actor.update_inventory(consumed_resource, -1, NULL)
        stats.agent_incr(actor_id, InventoryItemNames[consumed_resource] + ".used")
        strcpy(stat_name, actor.group_name.c_str())
        strcat(stat_name, ".")
        strcat(stat_name, InventoryItemNames[consumed_resource].c_str())
        strcat(stat_name, ".used")
        stats.agent_incr(actor_id, stat_name)

        actor.update_inventory(produced_resource, 1, NULL)
        stats.agent_incr(actor_id, InventoryItemNames[produced_resource] + ".gained")
        strcpy(stat_name, actor.group_name.c_str())
        strcat(stat_name, ".")
        strcat(stat_name, InventoryItemNames[produced_resource].c_str())
        strcat(stat_name, ".gained")
        stats.agent_incr(actor_id, stat_name)


        energy_gain = actor.update_energy(potential_energy_gain, rewards)
        stats.agent_add(actor_id, "energy.gained", energy_gain)
        strcpy(stat_name, actor.group_name.c_str())
        strcat(stat_name, ".")
        strcat(stat_name, "energy.gained")
        stats.agent_add(actor_id, stat_name, energy_gain)

    void obs(ObsType[:] obs):
        obs[0] = 1
        obs[1] = this.hp
        obs[2] = this.ready