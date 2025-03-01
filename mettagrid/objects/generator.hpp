#ifndef GENERATOR_HPP
#define GENERATOR_HPP

#include <vector>
#include <string>
#include "../grid_object.hpp"
#include "agent.hpp"
#include "constants.hpp"
#include "converter.hpp"
#include "event.hpp"

class Generator : public Converter {
public:
    Generator(GridCoord r, GridCoord c, ObjectConfig cfg, EventManager *event_manager) : Converter(r, c, cfg, ObjectType::GeneratorT, event_manager) {}

    static std::vector<std::string> feature_names() {
        auto names = Converter::feature_names();
        names[0] = "generator";
        return names;
    }
};

#endif
