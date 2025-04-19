#pragma once

#include <string>
#include <map>
#include <vector>
#include "grid_env.hpp"
#include "grid_object.hpp"
#include "objects/agent.hpp"

namespace mettagrid {

struct StatNames {
    std::string success;
    std::string first_use;
    std::string failure;

    std::map<TypeId, std::string> target;
    std::map<TypeId, std::string> target_first_use;
    std::vector<std::string> group;
};

class ActionHandler {
public:
    ActionHandler(const std::string& action_name) 
        : _action_name(action_name), _priority(0) {
        _stats.success = "action." + action_name;
        _stats.failure = "action." + action_name + ".failed";
        _stats.first_use = "action." + action_name + ".first_use";
    }

    void init(GridEnv* env) {
        this->env = env;
    }

    bool handle_action(
        unsigned int actor_id,
        GridObjectId actor_object_id,
        ActionArg arg) {
        
        Agent* actor = static_cast<Agent*>(env->grid().object(actor_object_id));

        if (actor->frozen > 0) {
            actor->stats.incr("status.frozen.ticks");
            actor->stats.incr("status.frozen.ticks", actor->group_name);
            actor->frozen -= 1;
            return false;
        }

        bool result = _handle_action(actor_id, actor, arg);

        if (result) {
            actor->stats.incr(_stats.success);
        } else {
            actor->stats.incr(_stats.failure);
            actor->stats.incr("action.failure_penalty");
            actor->reward[0] -= actor->action_failure_penalty;
            actor->stats.set_once(_stats.first_use, env->current_timestep());
        }

        return result;
    }

    unsigned char max_arg() const {
        return 0;
    }

    std::string action_name() const {
        return _action_name;
    }

protected:
    virtual bool _handle_action(
        unsigned int actor_id,
        Agent* actor,
        ActionArg arg) {
        return false;
    }

private:
    StatNames _stats;
    GridEnv* env;
    std::string _action_name;
    unsigned char _priority;
};

} // namespace mettagrid 
