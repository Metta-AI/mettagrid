from mettagrid.cpp_action_handler cimport CppActionHandler, cpp_ActionConfig

cdef extern from "put_recipe_items.hpp":
    cdef cppclass PutRecipeItems(CppActionHandler):
        PutRecipeItems(const cpp_ActionConfig& cfg)
