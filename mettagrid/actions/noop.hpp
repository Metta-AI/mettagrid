#ifndef NOOP_HPP
#define NOOP_HPP

#include <string>

#include "cpp_action_handler.hpp"
#include "objects/agent.hpp"

class Noop : public CppActionHandler {
public:
    Noop(const cpp_ActionConfig& cfg) : CppActionHandler(cfg, "noop") {}

    unsigned char cpp_max_arg() const override
    {
        return 0;
    }

protected:
    bool cpp_handle_action(unsigned int actor_id, Agent* actor, cpp_ActionArg arg) override
    {
        return true;
    }
};

#endif  // NOOP_HPP
