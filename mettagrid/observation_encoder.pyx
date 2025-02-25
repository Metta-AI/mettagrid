import numpy as np
import gymnasium as gym

from libc.stdio cimport printf
from libcpp.string cimport string
from libcpp.vector cimport vector

from mettagrid.grid_object cimport GridObject
from mettagrid.observation_encoder cimport ObservationEncoder, ObsType

from mettagrid.objects.constants cimport ObjectType

from mettagrid.objects.agent cimport Agent
from mettagrid.objects.converter cimport Converter
from mettagrid.objects.wall cimport Wall

cdef class MettaObservationEncoder(ObservationEncoder):
    cpdef obs_np_type(self):
        return np.uint8

    def __init__(self) -> None:
        self._offsets.resize(ObjectType.Count)
        self._type_feature_names.resize(ObjectType.Count)
        features = []

        self._type_feature_names[ObjectType.AgentT] = Agent.feature_names()
        self._type_feature_names[ObjectType.WallT] = Wall.feature_names()
        self._type_feature_names[ObjectType.GenericConverterT] = Converter.feature_names()

        for type_id in [ObjectType.AgentT, ObjectType.WallT, ObjectType.GenericConverterT]:
            self._offsets[type_id] = len(features)
            features.extend(self._type_feature_names[type_id])

        # These are all converters, so they share the same feature space
        for type_id in [ObjectType.AltarT, ObjectType.ArmoryT, ObjectType.FactoryT, ObjectType.GeneratorT, ObjectType.LabT, ObjectType.LaseryT, ObjectType.MineT, ObjectType.TempleT]:
            self._type_feature_names[type_id] = self._type_feature_names[ObjectType.GenericConverterT]
            self._offsets[type_id] = self._offsets[ObjectType.GenericConverterT]

        self._feature_names = features

    cdef encode(self, GridObject *obj, ObsType[:] obs):
        self._encode(obj, obs, self._offsets[obj._type_id])

    cdef _encode(self, GridObject *obj, ObsType[:] obs, unsigned int offset):
        obj.obs(&obs[offset])

    cdef vector[string] feature_names(self):
        return self._feature_names

cdef class MettaCompactObservationEncoder(MettaObservationEncoder):
    def __init__(self) -> None:
        super().__init__()
        self._num_features = 0
        for type_id in range(ObjectType.Count):
            self._num_features = max(self._num_features, len(self._type_feature_names[type_id]))

    cdef encode(self, GridObject *obj, ObsType[:] obs):
        self._encode(obj, obs, 0)
        obs[0] = obj._type_id + 1


    cpdef observation_space(self):
        type_info = np.iinfo(self.obs_np_type())

        return gym.spaces.Box(
                    low=type_info.min, high=type_info.max,
                    shape=(
                        self._num_features,
                        self._obs_height, self._obs_width),
            dtype=self.obs_np_type()
        )
