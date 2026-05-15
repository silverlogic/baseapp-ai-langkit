// HTTP layer for F02-S02 model-override saves.
//
// One stable per-node URL, relative to the admin change-root the widget
// already has via `topologyUrl`. The topology URL has shape
//     <change_root>/<pk>/topology/
// so trimming the trailing `topology/` segment gives us the prefix to which
// `nodes/<node_key>/model/` is appended. Mirrors `savePrompt.ts`.

import { readCsrfToken } from './savePrompt';
import type { ModelOverride } from './types';

export type ModelSaveErrorCode =
  | 'validation_error'
  | 'initializer_unknown'
  | 'model_not_in_catalog'
  | 'param_not_allowed'
  | 'param_invalid'
  | 'node_unknown'
  | 'runner_unregistered';

export interface ModelSaveError {
  code: ModelSaveErrorCode | string;
  message: string;
  details?: { disallowed?: string[]; invalid?: string[]; [k: string]: unknown };
}

export interface ModelSaveSuccess {
  override: ModelOverride;
}

export function buildSaveModelUrl(topologyUrl: string, nodeKey: string): string {
  const root = topologyUrl.endsWith('/')
    ? topologyUrl.slice(0, -1)
    : topologyUrl;
  const prefix = root.endsWith('/topology')
    ? root.slice(0, -'/topology'.length)
    : root;
  return `${prefix}/topology/nodes/${encodeURIComponent(nodeKey)}/model/`;
}

// Runner-level (F03-S01) sibling of `buildSaveModelUrl`. Targets the per-runner
// save endpoint `<pk>/topology/default-model/` (no node_key).
export function buildSaveRunnerDefaultModelUrl(topologyUrl: string): string {
  const root = topologyUrl.endsWith('/')
    ? topologyUrl.slice(0, -1)
    : topologyUrl;
  const prefix = root.endsWith('/topology')
    ? root.slice(0, -'/topology'.length)
    : root;
  return `${prefix}/topology/default-model/`;
}

export interface ModelSavePayload {
  initializer_key: string;
  model_id: string;
  params: Record<string, unknown>;
}

export async function saveModelOverride(
  saveUrl: string,
  payload: ModelSavePayload,
  fetchImpl: typeof fetch = window.fetch,
  documentRef: Document = document,
): Promise<
  | { ok: true; data: ModelSaveSuccess }
  | { ok: false; error: ModelSaveError; status: number }
> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  };
  const csrf = readCsrfToken(documentRef);
  if (csrf) headers['X-CSRFToken'] = csrf;

  let response: Response;
  try {
    response = await fetchImpl(saveUrl, {
      method: 'POST',
      credentials: 'same-origin',
      headers,
      body: JSON.stringify(payload),
    });
  } catch {
    return {
      ok: false,
      status: 0,
      error: { code: 'network_error', message: 'Network request failed.' },
    };
  }

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    /* keep body null */
  }
  if (response.ok) {
    return { ok: true, data: body as ModelSaveSuccess };
  }
  const error =
    (body as { error?: ModelSaveError })?.error ?? {
      code: 'unknown',
      message: `Request failed with status ${response.status}.`,
    };
  return { ok: false, status: response.status, error };
}

// Runner-level (F03-S01) sibling of `saveModelOverride`. Identical wire shape;
// the only difference is the URL the caller resolves via
// `buildSaveRunnerDefaultModelUrl`.
export function saveRunnerDefaultModel(
  saveUrl: string,
  payload: ModelSavePayload,
  fetchImpl: typeof fetch = window.fetch,
  documentRef: Document = document,
) {
  return saveModelOverride(saveUrl, payload, fetchImpl, documentRef);
}

// Reset (delete) the per-node override — DELETE on the same URL. Returns 200
// with `{override: null}` on success (idempotent if no override existed).
export async function resetModelOverride(
  saveUrl: string,
  fetchImpl: typeof fetch = window.fetch,
  documentRef: Document = document,
): Promise<
  | { ok: true }
  | { ok: false; error: ModelSaveError; status: number }
> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  const csrf = readCsrfToken(documentRef);
  if (csrf) headers['X-CSRFToken'] = csrf;

  let response: Response;
  try {
    response = await fetchImpl(saveUrl, {
      method: 'DELETE',
      credentials: 'same-origin',
      headers,
    });
  } catch {
    return {
      ok: false,
      status: 0,
      error: { code: 'network_error', message: 'Network request failed.' },
    };
  }

  if (response.ok) return { ok: true };

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    /* keep body null */
  }
  const error =
    (body as { error?: ModelSaveError })?.error ?? {
      code: 'unknown',
      message: `Request failed with status ${response.status}.`,
    };
  return { ok: false, status: response.status, error };
}

// Runner-level (F03-S01) sibling of `resetModelOverride`. Identical wire shape;
// the only difference is the URL the caller resolves via
// `buildSaveRunnerDefaultModelUrl`.
export function resetRunnerDefaultModel(
  saveUrl: string,
  fetchImpl: typeof fetch = window.fetch,
  documentRef: Document = document,
) {
  return resetModelOverride(saveUrl, fetchImpl, documentRef);
}
