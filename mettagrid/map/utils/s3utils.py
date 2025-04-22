import os


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
    # no strict dependency on boto3 in mettagrid, install if you need it
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


def list_objects(dir: str) -> list[str]:
    s3 = get_s3_client()
    bucket, key = parse_s3_uri(dir)

    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=key)

    uri_list: list[str] = []
    for page in pages:
        if "Contents" not in page:
            continue

        for obj in page["Contents"]:
            obj_key = obj["Key"]
            if obj_key == key or not obj_key.endswith(".yaml"):
                continue
            uri_list.append(f"s3://{bucket}/{obj_key}")

    return uri_list
