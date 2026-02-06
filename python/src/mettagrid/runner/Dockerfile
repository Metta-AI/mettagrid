FROM ubuntu:24.04

ARG METTAGRID_VERSION=""
ARG GIT_COMMIT=""
ENV GIT_COMMIT=${GIT_COMMIT}

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /uvx /bin/

# Install Nim via nimby (matches .nim-version / .nimby-version).
ARG NIMBY_VERSION=0.1.19
ARG NIM_VERSION=2.2.6
RUN curl -fsSL "https://github.com/treeform/nimby/releases/download/${NIMBY_VERSION}/nimby-Linux-X64" \
        -o /usr/local/bin/nimby && \
    chmod +x /usr/local/bin/nimby && \
    nimby use ${NIM_VERSION}
ENV PATH="/root/.nimby/nim/bin:$PATH"

# Install Python and create the executor venv with mettagrid.
RUN uv python install 3.12 && uv venv /opt/executor
RUN --mount=type=bind,target=/ctx \
    if ls /ctx/*.whl 1>/dev/null 2>&1; then \
        uv pip install --python /opt/executor/bin/python /ctx/*.whl; \
    elif [ -n "${METTAGRID_VERSION}" ]; then \
        uv pip install --python /opt/executor/bin/python "mettagrid==${METTAGRID_VERSION}"; \
    else \
        echo "ERROR: provide .whl in build context or set METTAGRID_VERSION" && exit 1; \
    fi

# Pre-warm uv cache with torch so per-policy venv creation is near-instant.
# mettagrid is already cached from the install above. Install torch into a
# throwaway venv just to populate the cache, then delete it.
RUN uv venv /tmp/cache-warm && \
    uv pip install --python /tmp/cache-warm/bin/python torch && \
    rm -rf /tmp/cache-warm

ENV PATH="/opt/executor/bin:$PATH"

ENTRYPOINT ["python", "-m", "mettagrid.runner.executor"]
