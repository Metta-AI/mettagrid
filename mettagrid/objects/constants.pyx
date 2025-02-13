from libcpp.vector cimport vector
from libcpp.string cimport string

cdef vector[string] InventoryItemNames = <vector[string]>[
    "r1",
    "r2",
    "r3"
]

cdef vector[string] ObjectTypeNames = <vector[string]>[
    "agent",
    "wall",
    "generator",
    "converter",
    "altar"
]

# cdef map[TypeId, GridLayer] ObjectLayers = <map[TypeId, GridLayer]>[
#     (TypeId.AgentT, GridLayer.Agent_Layer),
#     (TypeId.WallT, GridLayer.Object_Layer),
#     (TypeId.GeneratorT, GridLayer.Object_Layer),
#     (TypeId.ConverterT, GridLayer.Object_Layer),
#     (TypeId.AltarT, GridLayer.Object_Layer)
# ]


ObjectLayers = {
    ObjectType.AgentT: GridLayer.Agent_Layer,
    ObjectType.WallT: GridLayer.Object_Layer,
    ObjectType.GeneratorT: GridLayer.Object_Layer,
    ObjectType.ConverterT: GridLayer.Object_Layer,
    ObjectType.AltarT: GridLayer.Object_Layer,
}