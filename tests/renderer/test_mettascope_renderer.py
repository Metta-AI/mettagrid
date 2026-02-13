from mettagrid.renderer.mettascope import _extract_tutorial_overlay_phases


def test_extract_tutorial_overlay_phases_prefers_first_non_empty_list() -> None:
    overlay = _extract_tutorial_overlay_phases(
        {
            0: {"tutorial_overlay_phases": []},
            1: {"tutorial_overlay_phases": ["Step 1", "Step 2"]},
            2: {"tutorial_overlay_phases": ["Later Step"]},
        }
    )

    assert overlay == ["Step 1", "Step 2"]


def test_extract_tutorial_overlay_phases_ignores_non_dict_infos() -> None:
    overlay = _extract_tutorial_overlay_phases({0: "not-a-dict", 1: {"other_key": "value"}})
    assert overlay == []
