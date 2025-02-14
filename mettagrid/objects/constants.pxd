from libcpp.map cimport map
from libcpp.vector cimport vector
from libcpp.string cimport string
from mettagrid.grid_object cimport TypeId

cdef extern from "constants.hpp":
    cdef enum Events:
        Reset = 0

    cdef enum GridLayer:
        Agent_Layer = 0
        Object_Layer = 1

    cdef enum ObjectType:
        AgentT = 0
        WallT = 1
        GeneratorT = 2
        ConverterT = 3
        AltarT = 4
        Count = 5
        Resource_Count = 2

    cdef enum InventoryItem:
        r1 = 0
        r2 = 1
        r3 = 2
        InventoryCount = 3

    cdef vector[string] InventoryItemNames
    cdef map[TypeId, GridLayer] ObjectLayers
    cdef vector[string] ObjectTypeNames
