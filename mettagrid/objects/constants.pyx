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

ObjectLayers = {
    ObjectType.AgentT: GridLayer.Agent_Layer,
    ObjectType.WallT: GridLayer.Object_Layer,
    ObjectType.GeneratorT: GridLayer.Object_Layer,
    ObjectType.ConverterT: GridLayer.Object_Layer,
    ObjectType.AltarT: GridLayer.Object_Layer,
}