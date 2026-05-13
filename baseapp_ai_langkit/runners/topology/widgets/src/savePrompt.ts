// HTTP layer for F02-S01 prompt saves.
//
// Two stable per-target URLs, both relative to the admin change-root the
// widget already has via `topologyUrl`. The topology URL has shape
//     <change_root>/<pk>/topology/
// so trimming the trailing `topology/` segment gives us the prefix to which
// `nodes/<node_key>/usage-prompt/` (or `state-modifiers/<key>/`) is appended.

export type PromptSaveTarget =
  | { kind: 'usage_prompt' }
  | { kind: 'state_modifier'; key: string };

export type PromptSaveErrorCode =
  | 'missing_placeholders'
  | 'validation_error'
  | 'node_unknown'
  | 'runner_unregistered'
  | 'state_modifier_index_out_of_range'
  | 'prompt_target_unknown';

export interface PromptSaveError {
  code: PromptSaveErrorCode | string;
  message: string;
  details?: { missing?: string[]; messages?: string[]; [k: string]: unknown };
}

export interface PromptSaveSuccess {
  override: {
    text: string;
    saved_at: string | null;
  };
}

export function buildSavePromptUrl(
  topologyUrl: string,
  nodeKey: string,
  target: PromptSaveTarget,
): string {
  const root = topologyUrl.endsWith('/')
    ? topologyUrl.slice(0, -1)
    : topologyUrl;
  // Trim the trailing `/topology` so we can append the resource-style sub-path.
  const prefix = root.endsWith('/topology')
    ? root.slice(0, -'/topology'.length)
    : root;
  const encodedKey = encodeURIComponent(nodeKey);
  if (target.kind === 'usage_prompt') {
    return `${prefix}/topology/nodes/${encodedKey}/usage-prompt/`;
  }
  return `${prefix}/topology/nodes/${encodedKey}/state-modifiers/${encodeURIComponent(
    target.key,
  )}/`;
}

export function readCsrfToken(documentRef: Document = document): string | null {
  const match = documentRef.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export interface LayoutSaveSuccess {
  layout: {
    node_positions: Record<string, { x: number; y: number }>;
    saved_at: string | null;
  };
}

export function buildSaveLayoutUrl(topologyUrl: string): string {
  const trimmed = topologyUrl.endsWith('/')
    ? topologyUrl.slice(0, -1)
    : topologyUrl;
  return `${trimmed}/layout/`;
}

export async function saveTopologyLayout(
  saveUrl: string,
  positions: Record<string, { x: number; y: number }>,
  fetchImpl: typeof fetch = window.fetch,
  documentRef: Document = document,
): Promise<
  | { ok: true; data: LayoutSaveSuccess }
  | { ok: false; error: PromptSaveError; status: number }
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
      body: JSON.stringify({ node_positions: positions }),
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
    return { ok: true, data: body as LayoutSaveSuccess };
  }
  const error = (body as { error?: PromptSaveError })?.error ?? {
    code: 'unknown',
    message: `Request failed with status ${response.status}.`,
  };
  return { ok: false, status: response.status, error };
}


export async function savePrompt(
  saveUrl: string,
  text: string,
  fetchImpl: typeof fetch = window.fetch,
  documentRef: Document = document,
): Promise<{ ok: true; data: PromptSaveSuccess } | { ok: false; error: PromptSaveError; status: number }> {
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
      body: JSON.stringify({ text }),
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
    /* fall through; body stays null */
  }

  if (response.ok) {
    return { ok: true, data: body as PromptSaveSuccess };
  }
  const error =
    (body as { error?: PromptSaveError })?.error ?? {
      code: 'unknown',
      message: `Request failed with status ${response.status}.`,
    };
  return { ok: false, status: response.status, error };
}
