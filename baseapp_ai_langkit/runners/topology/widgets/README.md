# Runner Topology Widget

Pre-built React Flow bundle that renders a registered `LLMRunner`'s workflow topology in the Django admin (E01-F01-S02).

## What ships in the wheel

- `baseapp_ai_langkit/runners/static/runner_topology_widget.js` — built IIFE bundle that exposes `window.RunnerTopologyWidget`.
- `baseapp_ai_langkit/runners/static/runner_topology_widget.css` — built stylesheet.

The build emits both files **directly into** `runners/static/` — there is no separate `dist/` step to keep in sync. The widget source under `src/`, `test/`, the npm config, and `node_modules/` are not part of the wheel.

Consumers of `baseapp-ai-langkit` install the wheel and never run Node.

## Build

Contributors who change anything under `src/` must rebuild before pushing.
The package manager is **pnpm** — `pnpm-lock.yaml` is the canonical lockfile.

```sh
cd baseapp_ai_langkit/runners/topology/widgets
pnpm install --frozen-lockfile
pnpm run build
```

`pnpm run build` runs `esbuild` and copies the artifacts into `runners/static/`.
The build is deterministic — running it twice on the same source produces
byte-identical output.

CI re-runs the build and fails if the committed bundle is stale (`git diff --exit-code`).

## Test

```sh
pnpm test          # vitest run
pnpm run test:watch
```

## Public API

```ts
window.RunnerTopologyWidget.mount(targetEl, {
  topologyUrl: '/admin/.../topology/',
  legacyAdminUrl: '/admin/.../change/legacy/',
});
```

S03's admin template loads the JS + CSS via Django's `{% load static %}` and calls
`mount(...)` from a one-line inline script.

The widget fetches `topologyUrl` as a same-origin GET (Django session cookie carries auth;
no CSRF token). On any error code from S01 (`runner_unregistered`,
`topology_builder_not_declared`, `workflow_init_failed`, `unknown`) it renders an empty
canvas with a banner whose CTA navigates to `legacyAdminUrl`.
