from libcpp.vector cimport vector
from libcpp.string cimport string
from mettagrid.grid_env cimport StatsTracker
from mettagrid.observation_encoder cimport ObsType
from mettagrid.grid_object cimport GridCoord, GridLocation, GridObject
from .constants cimport ObjectType, GridLayer
from .metta_object cimport MettaObject, ObjectConfig
from .usable cimport Usable
from .agent cimport Agent

cdef cppclass Converter(Usable):
    short prey_r1_output_energy;
    short predator_r1_output_energy;
    short predator_r2_output_energy;

    inline Converter(GridCoord r, GridCoord c, ObjectConfig cfg):
        GridObject.init(ObjectType.ConverterT, GridLocation(r, c, GridLayer.Object_Layer))
        MettaObject.init_mo(cfg)
        # Usable.init_usable()
        this.prey_r1_output_energy = cfg[b"energy_output.r1.prey"]
        this.predator_r1_output_energy = cfg[b"energy_output.r1.predator"]
        this.predator_r2_output_energy = cfg[b"energy_output.r2.predator"]

    bint usable(const Agent *actor)

    void use(Agent *actor, unsigned int actor_id, StatsTracker stats, float *rewards)

    void obs(ObsType[:] obs)

    @staticmethod
    inline vector[string] feature_names():
        return ["converter", "converter:hp", "converter:ready"]