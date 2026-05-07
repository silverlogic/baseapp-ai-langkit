---
name: run-development-commands
version: 1.0.0
description: Translate developer intent into the correct Docker Compose commands for baseapp-ai-langkit (Django + uv project). Use this skill whenever the user wants to run tests, start the dev server, make or apply migrations, open a Django or database shell, lint or format code, run any manage.py command, install or add a Python dependency, or execute any other development command — even when they don't mention Docker explicitly.
triggers:
  - run tests
  - run server
  - make migrations
  - apply migrations
  - run lint
  - format code
  - open shell
  - manage.py
  - django command
  - docker compose run
  - pytest
  - install package
  - add dependency
  - uv add
  - sync runners
config:
  service: web
  compose_file: docker-compose.yml
---

# run-development-commands

## Purpose

All commands must run inside the `web` Docker service defined in `docker-compose.yml`. Never run Python, pytest, or Django management commands directly on the host — `langchain`, `langgraph`, `pgvector`, and the Postgres connection are wired through the container.

**Always detect container state before constructing a command:**

```bash
docker compose ps --status running --services | grep -qx web
```

- Running → `docker compose exec web <command>`
- Stopped → `docker compose run --rm web <command>`

In all patterns below, `<run>` means whichever form applies.

The web container's startup command runs `uv run --no-sync` already, so most commands inside the container are invoked directly. When the container is *stopped* (i.e. `docker compose run --rm`) you may need `uv run --no-sync` for some commands — prefer `python manage.py …` and `pytest …` first; fall back to `uv run --no-sync …` only if the binary isn't on PATH.

---

## Command Patterns

### Development Server

```bash
docker compose up          # db + web
docker compose up web      # web only (db must already be up)
```

The web container auto-runs `collectstatic`, `migrate`, then `runserver 0.0.0.0:8000`.

### Tests

```bash
docker compose <run> web pytest
docker compose <run> web pytest baseapp_ai_langkit/<area>/tests/
docker compose <run> web pytest baseapp_ai_langkit/<area>/tests/test_file.py::TestClass::test_method
docker compose <run> web pytest baseapp_ai_langkit/base/<area>/tests/
docker compose <run> web pytest -k "some_name"
docker compose <run> web pytest --reuse-db
docker compose <run> web pytest --cov --cov-report=term-missing
```

`pytest.ini` already sets `DJANGO_SETTINGS_MODULE = testproject.settings.test` and ignores `baseapp-backend/`. The settings module lives under `testproject/settings/`.

### Migrations

```bash
docker compose <run> web python manage.py makemigrations [<app_label>]
docker compose <run> web python manage.py migrate [<app_label>]
docker compose <run> web python manage.py showmigrations
docker compose <run> web python manage.py migrate --check   # exits non-zero if unapplied
```

App labels in this repo: `baseapp_ai_langkit_chats`, `baseapp_ai_langkit_runners`, `baseapp_ai_langkit_embeddings`, `baseapp_ai_langkit_vector_stores`, `baseapp_ai_langkit_slack`, `baseapp_mcp`.

### Sync runners (langkit-specific)

After adding or removing a `@register_runner`-decorated class, sync the DB-backed registry so the admin sees the new prompts:

```bash
docker compose <run> web python manage.py sync_runners
```

(See `baseapp_ai_langkit/runners/registry.py` and `LLMRunner.sync_runners`.)

### Lint & Format

```bash
docker compose <run> web black .          # line-length=100, target py38
docker compose <run> web isort .          # profile=black
docker compose <run> web flake8 .
docker compose <run> web pre-commit run --all-files
```

### Shells

```bash
docker compose <run> web python manage.py shell
docker compose <run> web python manage.py shell_plus    # django-extensions, autoloads models
docker compose <run> web python manage.py dbshell
```

### Dependencies (uv)

```bash
docker compose <run> web uv add <package>                       # add a new runtime dependency
docker compose <run> web uv add <package>==<ver>                # pin to a specific version
docker compose <run> web uv add --dev <package>                 # add a dev-only dependency
docker compose <run> web uv add --optional langkit <package>    # add to the langkit extra
docker compose <run> web uv add --optional mcp <package>        # add to the mcp extra
docker compose <run> web uv sync --all-extras                   # sync all dependencies from lockfile
```

`pyproject.toml` declares two optional extras: `langkit` (langchain/langgraph/slack-sdk/etc.) and `mcp` (FastMCP server stack). Pick the right extra when adding LLM- or MCP-specific deps.

### Other

```bash
docker compose <run> web python manage.py collectstatic --noinput
docker compose <run> web python manage.py <command> [args]
```

---

## Rules

1. **Never run on the host.** All Python, pytest, Black, Flake8, manage.py, and uv commands run inside the `web` container.
2. **Use `uv` for all dependency changes.** Never use `pip install` — always `uv add` inside Docker. Pick the right extra (`langkit`, `mcp`, `--dev`, or runtime).
3. **Always detect container state first.** Never hardcode `exec` or `run --rm`.
4. **Destructive commands need confirmation.** Before `migrate` on a non-local environment, `flush`, `reset`, dropping the pgvector schema, or any data-modifying command, confirm with the user.
5. **Clarify ambiguous requests and don't assume host env.** "run the app" → default to `docker compose up`; all env (including `OPENAI_API_KEY`, `BASEAPP_AI_LANGKIT_SLACK_*`) is injected via Docker Compose from `.env`.
6. **Sync runners after registry changes.** Adding/removing `@register_runner` classes without `sync_runners` leaves the admin out of sync.

---

## Edge Cases

**Unknown command** → check container state, then wrap as `exec web` or `run --rm web`.

**"Run tests faster"** → add `--reuse-db`. Never reuse the DB after migrations changed.

**Postgres-specific work (pgvector / langgraph checkpointer)** → the `db` image is `registry.tsl.io/base/postgres:15.3-pgvector_0.8.0`; if a developer asks you to swap it, confirm they have access to the TSL harbor or are providing a different pgvector-enabled image.

**Slack integration not loading** → check `BASEAPP_AI_LANGKIT_SLACK_BOT_USER_OAUTH_TOKEN`, `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_VERIFICATION_TOKEN`, `SLACK_SIGNING_SECRET` in `.env` (see README).
