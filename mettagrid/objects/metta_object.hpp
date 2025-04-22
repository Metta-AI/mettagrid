#ifndef METTA_OBJECT_HPP
#define METTA_OBJECT_HPP

#include <map>
#include <string>

#include "../cpp_grid_object.hpp"

typedef std::map<std::string, int> ObjectConfig;

class MettaObject : public CppGridObject {
public:
    unsigned int hp;

    void init_mo(ObjectConfig cfg)
    {
        this->hp = cfg["hp"];
    }

    virtual bool has_inventory()
    {  // TODO: make const
        return false;
    }

    virtual bool swappable() const
    {
        return false;
    }
};

#endif
