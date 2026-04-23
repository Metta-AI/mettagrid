from __future__ import annotations

from mettagrid.mapgen.scene import (
    AnySceneConfig,
    ChildrenAction,
    GridTransform,
    Scene,
    SceneConfig,
)


class RandomTransformConfig(SceneConfig):
    scene: AnySceneConfig


class RandomTransform(Scene[RandomTransformConfig]):
    def render(self) -> None:
        return

    def get_children(self) -> list[ChildrenAction]:
        return [
            ChildrenAction(
                scene=self.config.scene.model_copy(
                    update={"transform": GridTransform(self.rng.choice(list(GridTransform)))}
                ),
                where="full",
            )
        ]
