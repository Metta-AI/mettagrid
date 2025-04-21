from mettagrid.action_handler cimport ActionHandler

cdef extern from "put_recipe_items.hpp":
    cdef cppclass PutRecipeItems(ActionHandler):
        pass
