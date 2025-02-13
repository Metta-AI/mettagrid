# distutils: language=c++

from mettagrid.grid_object cimport GridObject

cdef cppclass MettaObject(GridObject):
    unsigned int hp

    void init_mo(ObjectConfig cfg):
        this.hp = cfg[b"hp"]

    bint is_usable_type():
        return False