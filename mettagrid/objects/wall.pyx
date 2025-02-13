# distutils: language=c++

# from mettagrid.objects.metta_object cimport MettaObject
from mettagrid.objects.metta_object import MettaObject

cdef cppclass Wall(MettaObject):
    bint is_true():
        return True