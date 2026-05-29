ASCII map files (`.map`) in this directory are loaded with PyYAML and validated with Pydantic via
`MapBuilderConfig.from_uri()`. They do not support Hydra features like `defaults` lists.

They are used in tests and experiment recipes.
