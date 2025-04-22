# distutils: language=c++

from mettagrid.grid_object cimport CppGridObject

cdef cppclass GridAgent(CppGridObject):
    pass
