#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_HANDLER_BINDINGS_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_HANDLER_BINDINGS_HPP_

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "core/game_value_config.hpp"
#include "core/query_config.hpp"
#include "core/types.hpp"
#include "handler/handler_config.hpp"
#include "handler/multi_handler.hpp"
#include "handler/territory_config.hpp"

namespace py = pybind11;

inline void bind_handler_config(py::module& m) {
  using namespace mettagrid;

  // GameValueScope enum
  py::enum_<GameValueScope>(m, "GameValueScope")
      .value("AGENT", GameValueScope::AGENT)
      .value("GAME", GameValueScope::GAME);

  // Typed GameValue configs
  py::class_<InventoryValueConfig>(m, "InventoryValueConfig")
      .def(py::init<>())
      .def_readwrite("scope", &InventoryValueConfig::scope)
      .def_readwrite("id", &InventoryValueConfig::id);

  py::class_<StatValueConfig>(m, "StatValueConfig")
      .def(py::init<>())
      .def_readwrite("scope", &StatValueConfig::scope)
      .def_readwrite("id", &StatValueConfig::id)
      .def_readwrite("delta", &StatValueConfig::delta)
      .def_readwrite("stat_name", &StatValueConfig::stat_name);

  py::class_<ConstValueConfig>(m, "ConstValueConfig")
      .def(py::init<>())
      .def_readwrite("value", &ConstValueConfig::value);

  py::class_<QueryInventoryValueConfig>(m, "QueryInventoryValueConfig")
      .def(py::init<>())
      .def_readwrite("id", &QueryInventoryValueConfig::id)
      .def(
          "set_query",
          [](QueryInventoryValueConfig& self, const QueryConfigHolder& q) { self.query = q.config; },
          py::arg("query"));

  py::class_<QueryCountValueConfig>(m, "QueryCountValueConfig")
      .def(py::init<>())
      .def(
          "set_query",
          [](QueryCountValueConfig& self, const QueryConfigHolder& q) { self.query = q.config; },
          py::arg("query"));

  py::class_<SumValueConfig, std::shared_ptr<SumValueConfig>>(m, "SumValueConfig")
      .def(py::init<>())
      .def_readwrite("values", &SumValueConfig::values)
      .def_readwrite("weights", &SumValueConfig::weights)
      .def_readwrite("log", &SumValueConfig::log)
      .def(
          "add_value",
          [](SumValueConfig& self, const GameValueConfig& value) { self.values.push_back(value); },
          py::arg("value"));

  py::class_<RatioValueConfig, std::shared_ptr<RatioValueConfig>>(m, "RatioValueConfig")
      .def(py::init<>())
      .def_readwrite("numerator", &RatioValueConfig::numerator)
      .def_readwrite("denominator", &RatioValueConfig::denominator);

  py::class_<MaxValueConfig, std::shared_ptr<MaxValueConfig>>(m, "MaxValueConfig")
      .def(py::init<>())
      .def_readwrite("values", &MaxValueConfig::values)
      .def(
          "add_value",
          [](MaxValueConfig& self, const GameValueConfig& value) { self.values.push_back(value); },
          py::arg("value"));

  py::class_<MinValueConfig, std::shared_ptr<MinValueConfig>>(m, "MinValueConfig")
      .def(py::init<>())
      .def_readwrite("values", &MinValueConfig::values)
      .def(
          "add_value",
          [](MinValueConfig& self, const GameValueConfig& value) { self.values.push_back(value); },
          py::arg("value"));

  // EntityRef enum
  py::enum_<EntityRef>(m, "EntityRef").value("actor", EntityRef::actor).value("target", EntityRef::target);

  // HandlerMode enum
  py::enum_<HandlerMode>(m, "HandlerMode").value("FirstMatch", HandlerMode::FirstMatch).value("All", HandlerMode::All);

  // StatsTarget enum
  py::enum_<StatsTarget>(m, "StatsTarget").value("game", StatsTarget::game).value("agent", StatsTarget::agent);

  // StatsEntity enum
  py::enum_<StatsEntity>(m, "StatsEntity").value("target", StatsEntity::target).value("actor", StatsEntity::actor);

  // Filter configs
  py::class_<VibeFilterConfig>(m, "VibeFilterConfig")
      .def(py::init<>())
      .def(py::init([](EntityRef entity, ObservationType vibe_id) {
             VibeFilterConfig cfg;
             cfg.entity = entity;
             cfg.vibe_id = vibe_id;
             return cfg;
           }),
           py::arg("entity") = EntityRef::target,
           py::arg("vibe_id") = 0)
      .def_readwrite("entity", &VibeFilterConfig::entity)
      .def_readwrite("vibe_id", &VibeFilterConfig::vibe_id);

  py::class_<ResourceFilterConfig>(m, "ResourceFilterConfig")
      .def(py::init<>())
      .def(py::init([](EntityRef entity, InventoryItem resource_id, InventoryQuantity min_amount) {
             ResourceFilterConfig cfg;
             cfg.entity = entity;
             cfg.resource_id = resource_id;
             cfg.min_amount = min_amount;
             return cfg;
           }),
           py::arg("entity") = EntityRef::target,
           py::arg("resource_id") = 0,
           py::arg("min_amount") = 1)
      .def_readwrite("entity", &ResourceFilterConfig::entity)
      .def_readwrite("resource_id", &ResourceFilterConfig::resource_id)
      .def_readwrite("min_amount", &ResourceFilterConfig::min_amount);

  // SharedTagPrefixFilter - checks if objects share tags with a common prefix
  py::class_<SharedTagPrefixFilterConfig>(m, "SharedTagPrefixFilterConfig")
      .def(py::init<>())
      .def(py::init([](std::vector<int> tag_ids) {
             SharedTagPrefixFilterConfig cfg;
             cfg.tag_ids = tag_ids;
             return cfg;
           }),
           py::arg("tag_ids") = std::vector<int>())
      .def_readwrite("tag_ids", &SharedTagPrefixFilterConfig::tag_ids);

  // TagPrefixFilter - checks if a single entity has any tag from a prefix group
  py::class_<TagPrefixFilterConfig>(m, "TagPrefixFilterConfig")
      .def(py::init<>())
      .def(py::init([](EntityRef entity, std::vector<int> tag_ids) {
             TagPrefixFilterConfig cfg;
             cfg.entity = entity;
             cfg.tag_ids = tag_ids;
             return cfg;
           }),
           py::arg("entity") = EntityRef::target,
           py::arg("tag_ids") = std::vector<int>())
      .def_readwrite("entity", &TagPrefixFilterConfig::entity)
      .def_readwrite("tag_ids", &TagPrefixFilterConfig::tag_ids);

  py::class_<QueryResourceFilterConfig>(m, "QueryResourceFilterConfig")
      .def(py::init<>())
      .def_readwrite("requirements", &QueryResourceFilterConfig::requirements)
      .def(
          "set_query",
          [](QueryResourceFilterConfig& self, const QueryConfigHolder& q) { self.query = q.config; },
          py::arg("query"));

  py::class_<GameValueFilterConfig>(m, "GameValueFilterConfig")
      .def(py::init<>())
      .def(py::init([](GameValueConfig value, float threshold, EntityRef entity) {
             GameValueFilterConfig cfg;
             cfg.value = value;
             cfg.threshold = threshold;
             cfg.entity = entity;
             return cfg;
           }),
           py::arg("value") = GameValueConfig{InventoryValueConfig{}},
           py::arg("threshold") = 0.0f,
           py::arg("entity") = EntityRef::target)
      .def_readwrite("value", &GameValueFilterConfig::value)
      .def_readwrite("threshold", &GameValueFilterConfig::threshold)
      .def_readwrite("entity", &GameValueFilterConfig::entity);

  py::class_<NegFilterConfig>(m, "NegFilterConfig")
      .def(py::init<>())
      .def_readwrite("inner", &NegFilterConfig::inner)
      .def(
          "add_vibe_filter",
          [](NegFilterConfig& self, const VibeFilterConfig& cfg) { self.inner.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_resource_filter",
          [](NegFilterConfig& self, const ResourceFilterConfig& cfg) { self.inner.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_game_value_filter",
          [](NegFilterConfig& self, const GameValueFilterConfig& cfg) { self.inner.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_shared_tag_prefix_filter",
          [](NegFilterConfig& self, const SharedTagPrefixFilterConfig& cfg) { self.inner.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_tag_prefix_filter",
          [](NegFilterConfig& self, const TagPrefixFilterConfig& cfg) { self.inner.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_neg_filter",
          [](NegFilterConfig& self, const NegFilterConfig& cfg) { self.inner.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_or_filter",
          [](NegFilterConfig& self, const OrFilterConfig& cfg) { self.inner.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_max_distance_filter",
          [](NegFilterConfig& self, const MaxDistanceFilterConfig& cfg) { self.inner.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_query_resource_filter",
          [](NegFilterConfig& self, const QueryResourceFilterConfig& cfg) { self.inner.push_back(cfg); },
          py::arg("filter"));

  py::class_<OrFilterConfig>(m, "OrFilterConfig")
      .def(py::init<>())
      .def_readwrite("inner", &OrFilterConfig::inner)
      .def(
          "add_vibe_filter",
          [](OrFilterConfig& self, const VibeFilterConfig& cfg) { self.inner.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_resource_filter",
          [](OrFilterConfig& self, const ResourceFilterConfig& cfg) { self.inner.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_game_value_filter",
          [](OrFilterConfig& self, const GameValueFilterConfig& cfg) { self.inner.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_shared_tag_prefix_filter",
          [](OrFilterConfig& self, const SharedTagPrefixFilterConfig& cfg) { self.inner.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_tag_prefix_filter",
          [](OrFilterConfig& self, const TagPrefixFilterConfig& cfg) { self.inner.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_neg_filter",
          [](OrFilterConfig& self, const NegFilterConfig& cfg) { self.inner.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_or_filter",
          [](OrFilterConfig& self, const OrFilterConfig& cfg) { self.inner.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_max_distance_filter",
          [](OrFilterConfig& self, const MaxDistanceFilterConfig& cfg) { self.inner.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_query_resource_filter",
          [](OrFilterConfig& self, const QueryResourceFilterConfig& cfg) { self.inner.push_back(cfg); },
          py::arg("filter"));

  // Mutation configs
  py::class_<ResourceDeltaMutationConfig>(m, "ResourceDeltaMutationConfig")
      .def(py::init<>())
      .def(py::init([](EntityRef entity, InventoryItem resource_id, InventoryDelta delta) {
             ResourceDeltaMutationConfig cfg;
             cfg.entity = entity;
             cfg.resource_id = resource_id;
             cfg.delta = delta;
             return cfg;
           }),
           py::arg("entity") = EntityRef::target,
           py::arg("resource_id") = 0,
           py::arg("delta") = 0)
      .def_readwrite("entity", &ResourceDeltaMutationConfig::entity)
      .def_readwrite("resource_id", &ResourceDeltaMutationConfig::resource_id)
      .def_readwrite("delta", &ResourceDeltaMutationConfig::delta);

  py::class_<ResourceTransferMutationConfig>(m, "ResourceTransferMutationConfig")
      .def(py::init<>())
      .def(py::init([](EntityRef source,
                       EntityRef destination,
                       InventoryItem resource_id,
                       InventoryDelta amount,
                       bool remove_source_when_empty) {
             ResourceTransferMutationConfig cfg;
             cfg.source = source;
             cfg.destination = destination;
             cfg.resource_id = resource_id;
             cfg.amount = amount;
             cfg.remove_source_when_empty = remove_source_when_empty;
             return cfg;
           }),
           py::arg("source") = EntityRef::actor,
           py::arg("destination") = EntityRef::target,
           py::arg("resource_id") = 0,
           py::arg("amount") = -1,
           py::arg("remove_source_when_empty") = false)
      .def_readwrite("source", &ResourceTransferMutationConfig::source)
      .def_readwrite("destination", &ResourceTransferMutationConfig::destination)
      .def_readwrite("resource_id", &ResourceTransferMutationConfig::resource_id)
      .def_readwrite("amount", &ResourceTransferMutationConfig::amount)
      .def_readwrite("remove_source_when_empty", &ResourceTransferMutationConfig::remove_source_when_empty);

  py::class_<ClearInventoryMutationConfig>(m, "ClearInventoryMutationConfig")
      .def(py::init<>())
      .def(py::init([](EntityRef entity, std::vector<InventoryItem> resource_ids) {
             ClearInventoryMutationConfig cfg;
             cfg.entity = entity;
             cfg.resource_ids = resource_ids;
             return cfg;
           }),
           py::arg("entity") = EntityRef::target,
           py::arg("resource_ids") = std::vector<InventoryItem>{})
      .def_readwrite("entity", &ClearInventoryMutationConfig::entity)
      .def_readwrite("resource_ids", &ClearInventoryMutationConfig::resource_ids);

  py::class_<AttackMutationConfig>(m, "AttackMutationConfig")
      .def(py::init<>())
      .def(py::init([](InventoryItem weapon_resource,
                       InventoryItem armor_resource,
                       InventoryItem health_resource,
                       int damage_multiplier_pct) {
             AttackMutationConfig cfg;
             cfg.weapon_resource = weapon_resource;
             cfg.armor_resource = armor_resource;
             cfg.health_resource = health_resource;
             cfg.damage_multiplier_pct = damage_multiplier_pct;
             return cfg;
           }),
           py::arg("weapon_resource"),
           py::arg("armor_resource"),
           py::arg("health_resource"),
           py::arg("damage_multiplier_pct") = 100)
      .def_readwrite("weapon_resource", &AttackMutationConfig::weapon_resource)
      .def_readwrite("armor_resource", &AttackMutationConfig::armor_resource)
      .def_readwrite("health_resource", &AttackMutationConfig::health_resource)
      .def_readwrite("damage_multiplier_pct", &AttackMutationConfig::damage_multiplier_pct);

  py::class_<StatsMutationConfig>(m, "StatsMutationConfig")
      .def(py::init<>())
      .def(py::init([](std::string stat_name, StatsTarget target, StatsEntity entity) {
             StatsMutationConfig cfg;
             cfg.stat_name = stat_name;
             cfg.target = target;
             cfg.entity = entity;
             return cfg;
           }),
           py::arg("stat_name") = "",
           py::arg("target") = StatsTarget::game,
           py::arg("entity") = StatsEntity::target)
      .def_readwrite("stat_name", &StatsMutationConfig::stat_name)
      .def_readwrite("target", &StatsMutationConfig::target)
      .def_readwrite("entity", &StatsMutationConfig::entity)
      .def_readwrite("source", &StatsMutationConfig::source);

  py::class_<AddTagMutationConfig>(m, "AddTagMutationConfig")
      .def(py::init<>())
      .def(py::init([](EntityRef entity, int tag_id) {
             AddTagMutationConfig cfg;
             cfg.entity = entity;
             cfg.tag_id = tag_id;
             return cfg;
           }),
           py::arg("entity") = EntityRef::target,
           py::arg("tag_id") = -1)
      .def_readwrite("entity", &AddTagMutationConfig::entity)
      .def_readwrite("tag_id", &AddTagMutationConfig::tag_id);

  py::class_<RemoveTagMutationConfig>(m, "RemoveTagMutationConfig")
      .def(py::init<>())
      .def(py::init([](EntityRef entity, int tag_id) {
             RemoveTagMutationConfig cfg;
             cfg.entity = entity;
             cfg.tag_id = tag_id;
             return cfg;
           }),
           py::arg("entity") = EntityRef::target,
           py::arg("tag_id") = -1)
      .def_readwrite("entity", &RemoveTagMutationConfig::entity)
      .def_readwrite("tag_id", &RemoveTagMutationConfig::tag_id);

  py::class_<RemoveTagsWithPrefixMutationConfig>(m, "RemoveTagsWithPrefixMutationConfig")
      .def(py::init<>())
      .def(py::init([](EntityRef entity, std::vector<int> tag_ids) {
             RemoveTagsWithPrefixMutationConfig cfg;
             cfg.entity = entity;
             cfg.tag_ids = tag_ids;
             return cfg;
           }),
           py::arg("entity") = EntityRef::target,
           py::arg("tag_ids") = std::vector<int>())
      .def_readwrite("entity", &RemoveTagsWithPrefixMutationConfig::entity)
      .def_readwrite("tag_ids", &RemoveTagsWithPrefixMutationConfig::tag_ids);

  py::class_<GameValueMutationConfig>(m, "GameValueMutationConfig")
      .def(py::init<>())
      .def(py::init([](GameValueConfig value, EntityRef target, GameValueConfig source) {
             GameValueMutationConfig cfg;
             cfg.value = value;
             cfg.target = target;
             cfg.source = source;
             return cfg;
           }),
           py::arg("value") = GameValueConfig{InventoryValueConfig{}},
           py::arg("target") = EntityRef::target,
           py::arg("source") = GameValueConfig{InventoryValueConfig{}})
      .def_readwrite("value", &GameValueMutationConfig::value)
      .def_readwrite("target", &GameValueMutationConfig::target)
      .def_readwrite("source", &GameValueMutationConfig::source);

  py::class_<QueryInventoryMutationConfig>(m, "QueryInventoryMutationConfig")
      .def(py::init<>())
      .def_readwrite("deltas", &QueryInventoryMutationConfig::deltas)
      .def_readwrite("source", &QueryInventoryMutationConfig::source)
      .def_readwrite("has_source", &QueryInventoryMutationConfig::has_source)
      .def_readwrite("transfer_stat_names", &QueryInventoryMutationConfig::transfer_stat_names)
      .def(
          "set_query",
          [](QueryInventoryMutationConfig& self, const QueryConfigHolder& q) { self.query = q.config; },
          py::arg("query"));

  // Move-specific filter configs (no fields, just marker types)
  py::class_<TargetLocEmptyFilterConfig>(m, "TargetLocEmptyFilterConfig").def(py::init<>());
  py::class_<TargetIsUsableFilterConfig>(m, "TargetIsUsableFilterConfig").def(py::init<>());

  // Move-specific mutation configs (no fields, just marker types)
  py::class_<RelocateMutationConfig>(m, "RelocateMutationConfig").def(py::init<>());
  py::class_<UseTargetMutationConfig>(m, "UseTargetMutationConfig").def(py::init<>());

  // HandlerConfig with methods to add filters and mutations
  py::class_<HandlerConfig, std::shared_ptr<HandlerConfig>>(m, "HandlerConfig")
      .def(py::init<>())
      .def(py::init<const std::string&>(), py::arg("name"))
      .def_readwrite("name", &HandlerConfig::name)
      // Add filter methods - each type wraps into the variant
      .def(
          "add_vibe_filter",
          [](HandlerConfig& self, const VibeFilterConfig& cfg) { self.filters.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_resource_filter",
          [](HandlerConfig& self, const ResourceFilterConfig& cfg) { self.filters.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_shared_tag_prefix_filter",
          [](HandlerConfig& self, const SharedTagPrefixFilterConfig& cfg) { self.filters.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_tag_prefix_filter",
          [](HandlerConfig& self, const TagPrefixFilterConfig& cfg) { self.filters.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_game_value_filter",
          [](HandlerConfig& self, const GameValueFilterConfig& cfg) { self.filters.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_neg_filter",
          [](HandlerConfig& self, const NegFilterConfig& cfg) { self.filters.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_or_filter",
          [](HandlerConfig& self, const OrFilterConfig& cfg) { self.filters.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_max_distance_filter",
          [](HandlerConfig& self, const MaxDistanceFilterConfig& cfg) { self.filters.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_query_resource_filter",
          [](HandlerConfig& self, const QueryResourceFilterConfig& cfg) { self.filters.push_back(cfg); },
          py::arg("filter"))
      // Add mutation methods - each type wraps into the variant
      .def(
          "add_resource_delta_mutation",
          [](HandlerConfig& self, const ResourceDeltaMutationConfig& cfg) { self.mutations.push_back(cfg); },
          py::arg("mutation"))
      .def(
          "add_resource_transfer_mutation",
          [](HandlerConfig& self, const ResourceTransferMutationConfig& cfg) { self.mutations.push_back(cfg); },
          py::arg("mutation"))
      .def(
          "add_clear_inventory_mutation",
          [](HandlerConfig& self, const ClearInventoryMutationConfig& cfg) { self.mutations.push_back(cfg); },
          py::arg("mutation"))
      .def(
          "add_attack_mutation",
          [](HandlerConfig& self, const AttackMutationConfig& cfg) { self.mutations.push_back(cfg); },
          py::arg("mutation"))
      .def(
          "add_stats_mutation",
          [](HandlerConfig& self, const StatsMutationConfig& cfg) { self.mutations.push_back(cfg); },
          py::arg("mutation"))
      .def(
          "add_add_tag_mutation",
          [](HandlerConfig& self, const AddTagMutationConfig& cfg) { self.mutations.push_back(cfg); },
          py::arg("mutation"))
      .def(
          "add_remove_tag_mutation",
          [](HandlerConfig& self, const RemoveTagMutationConfig& cfg) { self.mutations.push_back(cfg); },
          py::arg("mutation"))
      .def(
          "add_game_value_mutation",
          [](HandlerConfig& self, const GameValueMutationConfig& cfg) { self.mutations.push_back(cfg); },
          py::arg("mutation"))
      .def(
          "add_recompute_materialized_query_mutation",
          [](HandlerConfig& self, const RecomputeMaterializedQueryMutationConfig& cfg) {
            self.mutations.push_back(cfg);
          },
          py::arg("mutation"))
      .def(
          "add_query_inventory_mutation",
          [](HandlerConfig& self, const QueryInventoryMutationConfig& cfg) { self.mutations.push_back(cfg); },
          py::arg("mutation"))
      .def(
          "add_remove_tags_with_prefix_mutation",
          [](HandlerConfig& self, const RemoveTagsWithPrefixMutationConfig& cfg) { self.mutations.push_back(cfg); },
          py::arg("mutation"))
      // Move-specific filters
      .def(
          "add_target_loc_empty_filter",
          [](HandlerConfig& self, const TargetLocEmptyFilterConfig& cfg) { self.filters.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_target_is_usable_filter",
          [](HandlerConfig& self, const TargetIsUsableFilterConfig& cfg) { self.filters.push_back(cfg); },
          py::arg("filter"))
      // Move-specific mutations
      .def(
          "add_relocate_mutation",
          [](HandlerConfig& self, const RelocateMutationConfig& cfg) { self.mutations.push_back(cfg); },
          py::arg("mutation"))
      .def(
          "add_use_target_mutation",
          [](HandlerConfig& self, const UseTargetMutationConfig& cfg) { self.mutations.push_back(cfg); },
          py::arg("mutation"));

  // ResourceDelta for presence_deltas
  py::class_<ResourceDelta>(m, "ResourceDelta")
      .def(py::init<>())
      .def(py::init([](InventoryItem resource_id, InventoryDelta delta) {
             ResourceDelta cfg;
             cfg.resource_id = resource_id;
             cfg.delta = delta;
             return cfg;
           }),
           py::arg("resource_id") = 0,
           py::arg("delta") = 0)
      .def_readwrite("resource_id", &ResourceDelta::resource_id)
      .def_readwrite("delta", &ResourceDelta::delta);

  // AOEConfig inherits from HandlerConfig - filter/mutation methods are inherited
  py::class_<AOEConfig, HandlerConfig, std::shared_ptr<AOEConfig>>(m, "AOEConfig")
      .def(py::init<>())
      .def_readwrite("radius", &AOEConfig::radius)
      .def_readwrite("is_static", &AOEConfig::is_static)
      .def_readwrite("effect_self", &AOEConfig::effect_self)
      .def_readwrite("presence_deltas", &AOEConfig::presence_deltas);

  // TerritoryConfig - game-level territory type definition
  py::class_<TerritoryConfig>(m, "TerritoryConfig")
      .def(py::init<>())
      .def_readwrite("tag_prefix_ids", &TerritoryConfig::tag_prefix_ids)
      .def_readwrite("on_enter", &TerritoryConfig::on_enter)
      .def_readwrite("on_exit", &TerritoryConfig::on_exit)
      .def_readwrite("presence", &TerritoryConfig::presence);

  // TerritoryControlConfig - per-object influence on a territory type
  py::class_<TerritoryControlConfig>(m, "TerritoryControlConfig")
      .def(py::init<>())
      .def_readwrite("strength", &TerritoryControlConfig::strength)
      .def_readwrite("decay", &TerritoryControlConfig::decay)
      .def_readwrite("territory_index", &TerritoryControlConfig::territory_index);

  // Handler - single handler with filters and mutations
  py::class_<Handler, std::shared_ptr<Handler>>(m, "Handler")
      .def(py::init<const HandlerConfig&>(), py::arg("config"))
      .def("try_apply", py::overload_cast<HandlerContext&>(&Handler::try_apply))
      .def_property_readonly("name", &Handler::name);

  // MultiHandler - dispatches to multiple handlers
  py::class_<MultiHandler, Handler, std::shared_ptr<MultiHandler>>(m, "MultiHandler")
      .def(py::init<std::vector<std::shared_ptr<Handler>>, HandlerMode>(), py::arg("handlers"), py::arg("mode"))
      .def("try_apply", &MultiHandler::try_apply)
      .def_property_readonly("mode", &MultiHandler::mode)
      .def("__len__", &MultiHandler::size)
      .def("__bool__", [](const MultiHandler& m) { return !m.empty(); });
}

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_HANDLER_BINDINGS_HPP_
