import logging
import os
from dataclasses import dataclass
from datetime import datetime

from omegaconf import OmegaConf

from mettagrid.mettagrid_env import MettaGridEnv

logger = logging.getLogger(__name__)


def env_to_ascii(env: MettaGridEnv, border: bool = False) -> list[str]:
    grid = env._c_env.render_ascii()

    # convert to strings
    lines = ["".join(row) for row in grid]

    if border:
        width = len(lines[0])
        lines = ["┌" + "─" * width + "┐"]
        for row in lines:
            lines.append("│" + row + "│")
        lines.append("└" + "─" * width + "┘")

    return lines


@dataclass
class AsciiMap:
    metadata: dict
    lines: list[str]
    config: dict  # config that was used to generate the map; can contain unresolved OmegaConf resolvers
    resolved_config: dict  # resolved config

    def __str__(self) -> str:
        frontmatter = OmegaConf.to_yaml(
            {
                "metadata": self.metadata,
                "config": self.config,
                "resolved_config": self.resolved_config,
            }
        )
        content = frontmatter + "\n---\n" + "\n".join(self.lines) + "\n"
        return content

    @staticmethod
    def from_env(env: MettaGridEnv, gen_time: float) -> "AsciiMap":
        ascii_lines = env_to_ascii(env)

        resolved_config = env._env_cfg.game.map_builder
        config = env._cfg_template.game.map_builder
        metadata = {
            **env._env_cfg.mapgen.get("metadata", {}),
            "gen_time": gen_time,
            "timestamp": datetime.now().isoformat(),
        }
        return AsciiMap(metadata, ascii_lines, config, resolved_config)

    @staticmethod
    def from_uri(uri: str) -> "AsciiMap":
        content = load_from_uri(uri)

        # TODO - validate content in a more principled way
        (frontmatter, content) = content.split("---\n", 1)

        frontmatter = OmegaConf.load(frontmatter)
        metadata = frontmatter.metadata
        config = frontmatter.config
        resolved_config = frontmatter.resolved_config
        lines = content.split("\n")

        return AsciiMap(metadata, lines, config, resolved_config)

    def save(self, uri: str):
        save_to_uri(str(self), uri)


# The following functions are pretty generic, they can save or load any text to local filesystem or S3.


def is_s3_uri(uri: str) -> bool:
    return uri.startswith("s3://")


def parse_s3_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        raise ValueError(f"URI {uri} is not an S3 URI")

    s3_parts = uri[5:].split("/", 1)
    bucket = s3_parts[0]
    key = s3_parts[1]
    return bucket, key


def get_s3_client():
    import boto3

    # AWS_PROFILE won't be neceesary for most people, but some envirnoments can have multiple profiles
    # (Boto3 doesn't pick up the env variable automatically)
    session = boto3.Session(profile_name=os.environ.get("AWS_PROFILE", None))
    return session.client("s3")


def save_to_uri(text: str, uri: str):
    if is_s3_uri(uri):
        bucket, key = parse_s3_uri(uri)
        s3 = get_s3_client()
        s3.put_object(Bucket=bucket, Key=key, Body=text)
    else:
        with open(uri, "w") as f:
            f.write(text)


def load_from_uri(uri: str) -> str:
    if is_s3_uri(uri):
        bucket, key = parse_s3_uri(uri)
        s3 = get_s3_client()
        response = s3.get_object(Bucket=bucket, Key=key)
        return response["Body"].read().decode("utf-8")
    else:
        with open(uri, "r") as f:
            return f.read()
