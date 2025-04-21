import os


def test_cli_smoke():
    exit_status = os.system("python -m tools.mapgen --show ascii ./configs/game/map_builder/mapgen_simple.yaml")
    assert exit_status == 0

    exit_status = os.system("python -m tools.mapgen --show ascii ./configs/game/map_builder/NOT_A_CONFIG.yaml")
    assert exit_status != 0
