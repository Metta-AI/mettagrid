import urllib.request

from omegaconf import OmegaConf

# This script extracts maps from Dungeon Crawl Stone Soup into individual yaml scene files.


def fetch_simple():
    url = "https://raw.githubusercontent.com/crawl/crawl/master/crawl-ref/source/dat/des/arrival/simple.des"
    with urllib.request.urlopen(url) as response:
        return response.read().decode("utf-8")


def process_map_source(ascii_source):
    # split into lines
    lines = ascii_source.split("\n")
    # add space padding so that all lines are the same length
    max_length = max(len(line) for line in lines)
    lines = [line.ljust(max_length) for line in lines]

    # replace all symbols that are not `x` with spaces; replace `x` with `#`
    for i in range(len(lines)):
        original_line = lines[i]
        new_line = "".join(["#" if char == "x" else " " for char in original_line])
        lines[i] = new_line

    return "\n".join(lines)


def is_trivial(ascii_map):
    # if everything is blank, return true
    if all(line == " " * len(line) for line in ascii_map.split("\n")):
        return True

    return False


def get_maps():
    simple = fetch_simple()
    import re

    # Split by 'NAME:' but keep the delimiter at the beginning of the subsequent parts using a lookahead assertion.
    # If the string starts with 'NAME:', the first part will be an empty string.
    parts = re.split(r"(?=NAME:)", simple)

    maps = []
    for part in parts:
        if "NAME:" not in part:
            continue  # preamble before the first map

        name = part.split("NAME:")[1].split("\n")[0].strip()

        # Cut the part between "MAP" and "ENDMAP"
        start_marker = "MAP\n"
        end_marker = "\nENDMAP"
        start = part.find(start_marker)
        end = part.find(end_marker)
        if start != -1 and end != -1:
            ascii_source = part[start + len(start_marker) : end]
            ascii_map = process_map_source(ascii_source)
            if is_trivial(ascii_map):
                continue
            maps.append({"name": name, "map": ascii_map})

    return maps


def generate_scenes_from_dcss_maps():
    maps = get_maps()
    for map_entry in maps:
        config = OmegaConf.create(
            {
                "_target_": "mettagrid.map.scenes.convchain.ConvChain",
                "pattern_size": 3,
                "iterations": 10,
                "temperature": 1,
                "pattern": "\n".join([f"|{line}|" for line in map_entry["map"].split("\n")]),
            }
        )
        OmegaConf.save(config, f"configs/scenes/dcss/convchain-{map_entry['name']}.yaml")


if __name__ == "__main__":
    generate_scenes_from_dcss_maps()
