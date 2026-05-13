import { describe, expect, it, vi } from 'vitest';

import {
  buildSaveModelUrl,
  resetModelOverride,
  saveModelOverride,
} from '../src/saveModel';

const TOPOLOGY_URL = '/admin/baseapp_ai_langkit_runners/llmrunner/1/topology/';
const SAVE_URL =
  '/admin/baseapp_ai_langkit_runners/llmrunner/1/topology/nodes/general_llm/model/';

describe('buildSaveModelUrl', () => {
  it('appends nodes/<key>/model/ to the topology root', () => {
    expect(buildSaveModelUrl(TOPOLOGY_URL, 'general_llm')).toBe(SAVE_URL);
  });

  it('tolerates topology URL without trailing slash', () => {
    expect(buildSaveModelUrl(TOPOLOGY_URL.slice(0, -1), 'general_llm')).toBe(
      SAVE_URL,
    );
  });

  it('url-encodes the node key', () => {
    expect(buildSaveModelUrl(TOPOLOGY_URL, 'weird key/with slash')).toBe(
      '/admin/baseapp_ai_langkit_runners/llmrunner/1/topology/nodes/weird%20key%2Fwith%20slash/model/',
    );
  });
});

describe('saveModelOverride', () => {
  it('POSTs JSON body with initializer_key/model_id/params and the CSRF header when cookie set', async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        override: {
          initializer_key: 'openai',
          model_id: 'gpt-4o-mini',
          params: { temperature: 0.5 },
          saved_at: '2026-05-12T12:00:00Z',
          in_catalog: true,
        },
      }),
    } as unknown as Response));

    const documentRef = { cookie: 'csrftoken=abc; other=1' } as Document;

    const result = await saveModelOverride(
      SAVE_URL,
      {
        initializer_key: 'openai',
        model_id: 'gpt-4o-mini',
        params: { temperature: 0.5 },
      },
      fetchImpl as unknown as typeof fetch,
      documentRef,
    );

    expect(result.ok).toBe(true);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    const [url, init] = fetchImpl.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(SAVE_URL);
    expect(init.method).toBe('POST');
    expect((init.headers as Record<string, string>)['X-CSRFToken']).toBe('abc');
    expect(JSON.parse(init.body as string)).toEqual({
      initializer_key: 'openai',
      model_id: 'gpt-4o-mini',
      params: { temperature: 0.5 },
    });
  });

  it('returns the structured error envelope on 400', async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: false,
      status: 400,
      json: async () => ({
        error: {
          code: 'param_invalid',
          message: 'Params are out of range.',
          details: { invalid: ['temperature'] },
        },
      }),
    } as unknown as Response));

    const result = await saveModelOverride(
      SAVE_URL,
      { initializer_key: 'openai', model_id: 'gpt-4o-mini', params: { temperature: 3 } },
      fetchImpl as unknown as typeof fetch,
      { cookie: 'csrftoken=t' } as Document,
    );

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.status).toBe(400);
      expect(result.error.code).toBe('param_invalid');
      expect(result.error.details?.invalid).toEqual(['temperature']);
    }
  });

  it('synthesizes a network_error envelope on fetch rejection', async () => {
    const fetchImpl = vi.fn(async () => {
      throw new Error('boom');
    });
    const result = await saveModelOverride(
      SAVE_URL,
      { initializer_key: 'openai', model_id: 'gpt-4o-mini', params: {} },
      fetchImpl as unknown as typeof fetch,
      { cookie: '' } as Document,
    );
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.status).toBe(0);
      expect(result.error.code).toBe('network_error');
    }
  });
});

describe('resetModelOverride', () => {
  it('sends DELETE with the CSRF header and no body', async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ override: null }),
    } as unknown as Response));

    const result = await resetModelOverride(
      SAVE_URL,
      fetchImpl as unknown as typeof fetch,
      { cookie: 'csrftoken=tok' } as Document,
    );

    expect(result.ok).toBe(true);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    const [url, init] = fetchImpl.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(SAVE_URL);
    expect(init.method).toBe('DELETE');
    expect((init.headers as Record<string, string>)['X-CSRFToken']).toBe('tok');
    expect(init.body).toBeUndefined();
  });

  it('returns the structured error envelope on non-2xx', async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: false,
      status: 404,
      json: async () => ({
        error: { code: 'node_unknown', message: 'Node missing.' },
      }),
    } as unknown as Response));

    const result = await resetModelOverride(
      SAVE_URL,
      fetchImpl as unknown as typeof fetch,
      { cookie: 'csrftoken=t' } as Document,
    );

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.status).toBe(404);
      expect(result.error.code).toBe('node_unknown');
    }
  });

  it('synthesizes a network_error envelope on fetch rejection', async () => {
    const fetchImpl = vi.fn(async () => {
      throw new Error('boom');
    });
    const result = await resetModelOverride(
      SAVE_URL,
      fetchImpl as unknown as typeof fetch,
      { cookie: '' } as Document,
    );
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.status).toBe(0);
      expect(result.error.code).toBe('network_error');
    }
  });
});
