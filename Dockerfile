ARG PYTHON_VERSION=3.11.0

FROM registry.tsl.io/base/base-django:${PYTHON_VERSION} AS base

FROM base AS baseos
# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Disable Python downloads, because we want to use the system interpreter
# across images. If using a managed Python version, it needs to be
# copied from the build image into the final image;
ENV UV_PYTHON_DOWNLOADS=0

# Ensure installed tools can be executed out of the box
ENV UV_TOOL_BIN_DIR=/usr/local/bin

# Set venv path
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="$UV_PROJECT_ENVIRONMENT/bin:$PATH"

RUN mkdir -p /usr/src/app

COPY . /usr/src/app

WORKDIR /usr/src/app

# Install uv and sync dependencies (all extras + dev for tests)
COPY --from=ghcr.io/astral-sh/uv:0.10.9 /uv /uvx /bin/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --python "${PYTHON_VERSION}" --frozen --no-install-project --no-editable --all-extras --group dev
