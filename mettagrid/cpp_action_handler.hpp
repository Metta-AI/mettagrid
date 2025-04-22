#ifndef CPP_ACTION_HANDLER_HPP
#define CPP_ACTION_HANDLER_HPP

#include <map>
#include <string>
#include <vector>

#include "cpp_grid.hpp"
#include "cpp_grid_object.hpp"
#include "objects/agent.hpp"
#include "objects/constants.hpp"

struct CppStatNames {
    std::string success;
    std::string first_use;
    std::string failure;

    std::map<cpp_TypeId, std::string> target;
    std::map<cpp_TypeId, std::string> target_first_use;
    std::vector<std::string> group;
};

typedef unsigned char cpp_ActionArg;
typedef std::map<std::string, int> cpp_ActionConfig;

class CppActionHandler {
public:
    unsigned char priority;
    CppGrid* _grid;

    CppActionHandler(const cpp_ActionConfig& cfg, const std::string& action_name)
        : priority(0), _action_name(action_name)
    {
        _stats.success = "action." + action_name;
        _stats.failure = "action." + action_name + ".failed";
        _stats.first_use = "action." + action_name + ".first_use";

        for (cpp_TypeId t = 0; t < ObjectType::Count; t++) {
            _stats.target[t] = _stats.success + "." + ObjectTypeNames[t];
            _stats.target_first_use[t] = _stats.first_use + "." + ObjectTypeNames[t];
        }
    }

    virtual ~CppActionHandler() = default;

    void cpp_init(CppGrid* grid)
    {
        _grid = grid;
    }

    bool cpp_handle_action(unsigned int actor_id, cpp_GridObjectId actor_object_id, cpp_ActionArg arg,
                           unsigned int current_timestep)
    {
        Agent* actor = static_cast<Agent*>(_grid->object(actor_object_id));

        if (actor->frozen > 0) {
            actor->stats.incr("status.frozen.ticks");
            actor->stats.incr("status.frozen.ticks", actor->group_name);
            actor->frozen -= 1;
            return false;
        }

        bool result = cpp_handle_action(actor_id, actor, arg);

        if (result) {
            actor->stats.incr(_stats.success);
        }
        else {
            actor->stats.incr(_stats.failure);
            actor->stats.incr("action.failure_penalty");
            *actor->reward -= actor->action_failure_penalty;
            actor->stats.set_once(_stats.first_use, current_timestep);
        }

        return result;
    }

    virtual unsigned char cpp_max_arg() const
    {
        return 0;
    }

    std::string cpp_action_name() const
    {
        return _action_name;
    }

protected:
    virtual bool cpp_handle_action(unsigned int actor_id, Agent* actor, cpp_ActionArg arg) = 0;

    CppStatNames _stats;
    std::string _action_name;
};

class CppDefaultActionHandler : public CppActionHandler {
public:
    CppDefaultActionHandler(const cpp_ActionConfig& cfg, const std::string& action_name)
        : CppActionHandler(cfg, action_name)
    {
    }

    // Implement the required pure virtual method
    virtual bool cpp_handle_action(unsigned int actor_id, Agent* actor, cpp_ActionArg arg) override
    {
        // Default implementation - modify according to your needs
        return false;  // Or whatever default behavior makes sense
    }
};

#endif  // CPP_ACTION_HANDLER_HPP
