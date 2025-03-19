#ifndef GENERATOR_HPP
#define GENERATOR_HPP

#include <vector>
#include <string>
#include "../grid_object.hpp"
#include "agent.hpp"
#include "constants.hpp"
#include "converter.hpp"

class Generator : public Converter {
public:
    int color;
    Generator(GridCoord r, GridCoord c, ObjectConfig cfg) : Converter(r, c, cfg, ObjectType::GeneratorT), color(cfg["color"]) {}

    void obs(ObsType *obs, const std::vector<unsigned int> &offsets) const override {
        Converter::obs(obs, offsets);
        obs[offsets[3+InventoryItem::InventoryCount]] = this->color;
    }

    static std::vector<std::string> feature_names() {
        auto names = Converter::feature_names();
        names[0] = "generator";
        names.push_back("color");
        return names;
    }
};

#endif
