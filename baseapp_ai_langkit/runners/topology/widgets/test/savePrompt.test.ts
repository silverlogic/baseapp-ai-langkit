import { describe, expect, it, vi } from 'vitest';

import {
  buildSaveLayoutUrl,
  buildSavePromptUrl,
  readCsrfToken,
  savePrompt,
  saveTopologyLayout,
} from '../src/savePrompt';

describe('buildSavePromptUrl', () => {
  it('builds the usage-prompt URL by replacing /topology/ with the per-target sub-path', () => {
    const url = buildSavePromptUrl(
      '/admin/baseapp_ai_langkit_runners/llmrunner/42/topology/',
      'general_llm',
      { kind: 'usage_prompt' },
    );
    expect(url).toBe(
      '/admin/baseapp_ai_langkit_runners/llmrunner/42/topology/nodes/general_llm/usage-prompt/',
    );
  });

  it('builds the state-modifier URL with the integer-string key', () => {
    const url = buildSavePromptUrl(
      '/admin/baseapp_ai_langkit_runners/llmrunner/42/topology/',
      'general_llm',
      { kind: 'state_modifier', key: '0' },
    );
    expect(url).toBe(
      '/admin/baseapp_ai_langkit_runners/llmrunner/42/topology/nodes/general_llm/state-modifiers/0/',
    );
  });

  it('URL-encodes the node key', () => {
    const url = buildSavePromptUrl(
      '/admin/.../topology/',
      'a/b c',
      { kind: 'usage_prompt' },
    );
    expect(url).toContain('a%2Fb%20c');
  });

  it('accepts a topology URL without a trailing slash', () => {
    const url = buildSavePromptUrl(
      '/admin/.../topology',
      'n',
      { kind: 'usage_prompt' },
    );
    expect(url).toBe('/admin/.../topology/nodes/n/usage-prompt/');
  });
});

describe('readCsrfToken', () => {
  it('extracts the csrftoken cookie value', () => {
    const doc = { cookie: 'foo=bar; csrftoken=abc-123; baz=qux' } as Document;
    expect(readCsrfToken(doc)).toBe('abc-123');
  });

  it('returns null when no csrftoken cookie is present', () => {
    const doc = { cookie: 'foo=bar' } as Document;
    expect(readCsrfToken(doc)).toBeNull();
  });
});

describe('savePrompt', () => {
  const VALID_URL = '/admin/x/y/topology/nodes/n/usage-prompt/';
  const docWithCsrf = { cookie: 'csrftoken=tok-1' } as Document;

  it('POSTs JSON with CSRF header, returns ok+data on 200', async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ override: { text: 't', saved_at: '2026-05-11T00:00:00Z' } }),
    } as unknown as Response));

    const result = await savePrompt(VALID_URL, 't', fetchImpl as unknown as typeof fetch, docWithCsrf);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.override.text).toBe('t');
    }
    expect(fetchImpl).toHaveBeenCalledWith(
      VALID_URL,
      expect.objectContaining({
        method: 'POST',
        credentials: 'same-origin',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
          'X-CSRFToken': 'tok-1',
        }),
        body: JSON.stringify({ text: 't' }),
      }),
    );
  });

  it('returns ok=false with the structured error on 400', async () => {
    const errorBody = {
      error: {
        code: 'missing_placeholders',
        message: 'missing {topic}',
        details: { missing: ['{topic}'] },
      },
    };
    const fetchImpl = vi.fn(async () => ({
      ok: false,
      status: 400,
      json: async () => errorBody,
    } as unknown as Response));

    const result = await savePrompt(VALID_URL, '', fetchImpl as unknown as typeof fetch, docWithCsrf);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.status).toBe(400);
      expect(result.error.code).toBe('missing_placeholders');
      expect(result.error.details?.missing).toEqual(['{topic}']);
    }
  });

  it('synthesizes a network_error on fetch throw', async () => {
    const fetchImpl = vi.fn(async () => {
      throw new Error('offline');
    });
    const result = await savePrompt(VALID_URL, 't', fetchImpl as unknown as typeof fetch, docWithCsrf);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.code).toBe('network_error');
    }
  });

  it('omits the CSRF header when no csrftoken cookie is set', async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ override: { text: 't', saved_at: null } }),
    } as unknown as Response));

    await savePrompt(VALID_URL, 't', fetchImpl as unknown as typeof fetch, { cookie: '' } as Document);
    const init = (fetchImpl.mock.calls[0]?.[1] ?? {}) as RequestInit;
    const headers = (init.headers ?? {}) as Record<string, string>;
    expect(Object.keys(headers)).not.toContain('X-CSRFToken');
  });
});

describe('buildSaveLayoutUrl', () => {
  it('appends layout/ to the topology URL (with trailing slash)', () => {
    expect(
      buildSaveLayoutUrl('/admin/x/y/llmrunner/42/topology/'),
    ).toBe('/admin/x/y/llmrunner/42/topology/layout/');
  });

  it('appends layout/ to the topology URL (without trailing slash)', () => {
    expect(buildSaveLayoutUrl('/admin/x/y/llmrunner/42/topology')).toBe(
      '/admin/x/y/llmrunner/42/topology/layout/',
    );
  });
});

describe('saveTopologyLayout', () => {
  const SAVE_URL = '/admin/x/y/llmrunner/42/topology/layout/';
  const DOC_WITH_CSRF = { cookie: 'csrftoken=tok-99' } as Document;

  it('POSTs node_positions JSON with the CSRF header, returns ok+data on 200', async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        layout: {
          node_positions: { a: { x: 10, y: 20 } },
          saved_at: '2026-05-11T00:00:00Z',
        },
      }),
    } as unknown as Response));

    const result = await saveTopologyLayout(
      SAVE_URL,
      { a: { x: 10, y: 20 } },
      fetchImpl as unknown as typeof fetch,
      DOC_WITH_CSRF,
    );

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.layout.node_positions).toEqual({ a: { x: 10, y: 20 } });
    }
    expect(fetchImpl).toHaveBeenCalledWith(
      SAVE_URL,
      expect.objectContaining({
        method: 'POST',
        credentials: 'same-origin',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
          'X-CSRFToken': 'tok-99',
        }),
        body: JSON.stringify({ node_positions: { a: { x: 10, y: 20 } } }),
      }),
    );
  });

  it('POSTs empty positions to clear the layout (Reset to auto path)', async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        layout: { node_positions: {}, saved_at: '2026-05-11T00:00:00Z' },
      }),
    } as unknown as Response));

    const result = await saveTopologyLayout(
      SAVE_URL,
      {},
      fetchImpl as unknown as typeof fetch,
      DOC_WITH_CSRF,
    );
    expect(result.ok).toBe(true);
    expect(fetchImpl).toHaveBeenCalledWith(
      SAVE_URL,
      expect.objectContaining({
        body: JSON.stringify({ node_positions: {} }),
      }),
    );
  });

  it('returns ok=false with the structured error on 400', async () => {
    const errorBody = {
      error: { code: 'validation_error', message: 'bad shape' },
    };
    const fetchImpl = vi.fn(async () => ({
      ok: false,
      status: 400,
      json: async () => errorBody,
    } as unknown as Response));

    const result = await saveTopologyLayout(
      SAVE_URL,
      { a: { x: 0, y: 0 } },
      fetchImpl as unknown as typeof fetch,
      DOC_WITH_CSRF,
    );
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.code).toBe('validation_error');
    }
  });

  it('synthesizes a network_error on fetch throw', async () => {
    const fetchImpl = vi.fn(async () => {
      throw new Error('offline');
    });
    const result = await saveTopologyLayout(
      SAVE_URL,
      {},
      fetchImpl as unknown as typeof fetch,
      DOC_WITH_CSRF,
    );
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.code).toBe('network_error');
    }
  });
});
