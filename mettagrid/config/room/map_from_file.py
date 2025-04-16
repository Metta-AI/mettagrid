import numpy as np
import os
import random
from mettagrid.config.room.room import Room
import boto3
from botocore.exceptions import NoCredentialsError
import zipfile

def download_from_s3(s3_path: str, save_path: str):
    if not s3_path.startswith("s3://"):
        raise ValueError(f"Invalid S3 path: {s3_path}. Must start with s3://")

    s3_parts = s3_path[5:].split("/", 1)
    if len(s3_parts) < 2:
        raise ValueError(f"Invalid S3 path: {s3_path}. Must be in format s3://bucket/path")

    bucket = s3_parts[0]
    key = s3_parts[1]

    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        # Download the file directly to disk
        s3_client = boto3.client("s3")
        s3_client.download_file(Bucket=bucket, Key=key, Filename=save_path)
        print(f"Successfully downloaded s3://{bucket}/{key} to {save_path}")


    except NoCredentialsError as e:
        raise e
    except Exception as e:
        raise e

class MapFromFile(Room):
    def __init__(self, dir, border_width: int = 0, border_object: str = "wall"):
        zipped_dir = dir + ".zip"
        if not os.path.exists(dir) and not os.path.exists(zipped_dir):
            s3_path = f"s3://softmax-public/metta/training/{zipped_dir}"
            download_from_s3(s3_path, zipped_dir)
        if not os.path.exists(dir) and os.path.exists(zipped_dir):
            with zipfile.ZipFile(zipped_dir, 'r') as zip_ref:
                zip_ref.extractall(os.path.dirname(dir))
        self.files = os.listdir(dir)
        self.dir = dir
        super().__init__(border_width=border_width, border_object=border_object)

    def _build(self):
        uri = np.random.choice(self.files)
        level = np.load(f"{self.dir}/{uri}")
        area = level.shape[0] * level.shape[1]
        num_hearts = area // random.randint(45, 150)

        # Find valid empty spaces surrounded by empty
        valid_positions = []
        for i in range(1, level.shape[0]-1):
            for j in range(1, level.shape[1]-1):
                if level[i,j] == "empty":
                    # Check if position is accessible from at least one direction
                    if (level[i-1,j] == "empty" or
                        level[i+1,j] == "empty" or
                        level[i,j-1] == "empty" or
                        level[i,j+1] == "empty"):
                        valid_positions.append((i,j))

        # Randomly place hearts in valid positions
        positions = random.sample(valid_positions, min(num_hearts, len(valid_positions)))
        for pos in positions:
            level[pos] = "altar"
        self._level = level
        return self._level
