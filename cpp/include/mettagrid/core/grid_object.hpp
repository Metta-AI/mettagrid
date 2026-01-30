#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_GRID_OBJECT_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_GRID_OBJECT_HPP_

#include <cstdint>
#include <memory>
#include <set>
#include <span>
#include <string>
#include <unordered_map>
#include <vector>

#include "core/types.hpp"
#include "handler/handler_config.hpp"
#include "objects/alignable.hpp"
#include "objects/constants.hpp"
#include "objects/has_inventory.hpp"
#include "objects/has_vibe.hpp"
#include "objects/inventory_config.hpp"
#include "objects/usable.hpp"

// Forward declaration
class ObservationEncoder;

using TypeId = ObservationType;
using ObservationCoord = ObservationType;
using Vibe = ObservationType;

struct PartialObservationToken {
  ObservationType feature_id = EmptyTokenByte;
  ObservationType value = EmptyTokenByte;
};

// These may make more sense in observation_encoder.hpp, but we need to include that
// header in a lot of places, and it's nice to have these types defined in one place.
struct alignas(1) ObservationToken {
  ObservationType location = EmptyTokenByte;
  ObservationType feature_id = EmptyTokenByte;
  ObservationType value = EmptyTokenByte;
};

// The alignas should make sure of this, but let's be explicit.
// We're going to be reinterpret_casting things to this type, so
// it'll be bad if the compiler pads this type.
static_assert(sizeof(ObservationToken) == 3 * sizeof(uint8_t), "ObservationToken must be 3 bytes");

using ObservationTokens = std::span<ObservationToken>;

class GridLocation {
public:
  GridCoord r;
  GridCoord c;

  inline GridLocation(GridCoord r, GridCoord c) : r(r), c(c) {}
  inline GridLocation() : r(0), c(0) {}

  inline bool operator==(const GridLocation& other) const {
    return r == other.r && c == other.c;
  }
};

struct GridObjectConfig {
  TypeId type_id;
  std::string type_name;
  std::string name;  // Instance name (defaults to type_name if empty)
  std::vector<int> tag_ids;
  ObservationType initial_vibe;
  int collective_id = -1;  // Collective ID for initial alignment (-1 = none)
  InventoryConfig inventory_config;
  std::unordered_map<InventoryItem, InventoryQuantity> initial_inventory;

  // Two types of handlers on GridObject:
  // - on_use: Triggered when agent uses/activates this object (context: actor=agent, target=this)
  // - aoe: Triggered per-tick for objects within radius (context: actor=this, target=affected)
  std::vector<mettagrid::HandlerConfig> on_use_handlers;
  std::vector<mettagrid::AOEConfig> aoe_configs;

  GridObjectConfig(TypeId type_id, const std::string& type_name, ObservationType initial_vibe = 0)
      : type_id(type_id),
        type_name(type_name),
        name(""),
        tag_ids({}),
        initial_vibe(initial_vibe),
        inventory_config(),
        on_use_handlers(),
        aoe_configs() {}

  virtual ~GridObjectConfig() = default;
};

// Forward declarations
namespace mettagrid {
class Handler;
class TagIndex;
}  // namespace mettagrid

class GridObject : public HasVibe, public Alignable, public HasInventory, public Usable {
public:
  GridObjectId id{};
  GridLocation location{};
  TypeId type_id{};
  std::string type_name;  // Class type (e.g., "hub")
  std::string name;       // Instance name (e.g., "carbon_extractor"), defaults to type_name
  std::set<int> tag_ids;

  // Constructor with optional inventory config (defaults to empty)
  explicit GridObject(const InventoryConfig& inv_config = InventoryConfig()) : HasInventory(inv_config) {}

  ~GridObject() override = default;

  void init(TypeId object_type_id,
            const std::string& object_type_name,
            const GridLocation& object_location,
            const std::vector<int>& tags,
            ObservationType object_vibe = 0,
            const std::string& object_name = "");

  // Set handlers for each type
  void set_on_use_handlers(std::vector<std::shared_ptr<mettagrid::Handler>> handlers);
  void set_aoe_configs(std::vector<mettagrid::AOEConfig> configs);

  // Check if this object has any handlers of each type
  bool has_on_use_handlers() const;

  // Get AOE configs for AOE processing
  const std::vector<mettagrid::AOEConfig>& aoe_configs() const;

  // Override onUse to try on_use handlers
  bool onUse(Agent& actor, ActionArg arg) override;

  // Tag mutation methods
  bool has_tag(int tag_id) const;
  void add_tag(int tag_id);
  void remove_tag(int tag_id);

  // Set the tag index reference (called by MettaGrid)
  void set_tag_index(mettagrid::TagIndex* index) {
    _tag_index = index;
  }

  // Set observation encoder for inventory token encoding
  void set_obs_encoder(const ObservationEncoder* encoder) {
    obs_encoder = encoder;
  }

  // Returns observable features for this object (collective, tags, vibe, inventory)
  // Subclasses should call this base implementation and append their specific features
  virtual std::vector<PartialObservationToken> obs_features() const;

  const ObservationEncoder* obs_encoder = nullptr;

  // Set grid access (used for removing depleted objects from grid)
  void set_grid(class Grid* grid_ptr) {
    _grid = grid_ptr;
  }

  // Get grid pointer
  class Grid* grid() const {
    return _grid;
  }

protected:
  std::vector<std::shared_ptr<mettagrid::Handler>> _on_use_handlers;
  std::vector<mettagrid::AOEConfig> _aoe_configs;
  class Grid* _grid = nullptr;

private:
  mettagrid::TagIndex* _tag_index = nullptr;
};

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_GRID_OBJECT_HPP_
