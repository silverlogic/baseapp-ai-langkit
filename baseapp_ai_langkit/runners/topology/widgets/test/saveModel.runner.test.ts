// F03-S01 saveModel runner-level helpers.
//
// Mirrors saveModel.test.ts's per-node coverage one rung higher: URL builder,
// happy-path POST, error envelope passthrough, CSRF header, network_error
// synthesis, idempotent DELETE.

import { describe, expect, it, vi } from 'vitest';

import {
  buildSaveRunnerDefaultModelUrl,
  resetRunnerDefaultModel,
  saveRunnerDefaultModel,
} from '../src/saveModel';

const TOPOLOGY_URL = '/admin/baseapp_ai_langkit_runners/llmrunner/1/topology/';
const SAVE_URL =
  '/admin/baseapp_ai_langkit_runners/llmrunner/1/topology/default-model/';

describe('buildSaveRunnerDefaultModelUrl', () => {
  it('appends default-model/ to the topology root', () => {
    expect(buildSaveRunnerDefaultModelUrl(TOPOLOGY_URL)).toBe(SAVE_URL);
  });

  it('tolerates topology URL without trailing slash', () => {
    expect(buildSaveRunnerDefaultModelUrl(TOPOLOGY_URL.slice(0, -1))).toBe(
      SAVE_URL,
    );
  });

  it('does not include a node_key segment', () => {
    const url = buildSaveRunnerDefaultModelUrl(TOPOLOGY_URL);
    expect(url).not.toMatch(/\/nodes\//);
  });
});

describe('saveRunnerDefaultModel', () => {
  it('POSTs JSON body with initializer_key/model_id/params and CSRF header', async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        override: {
          initializer_key: 'anthropic',
          model_id: 'claude-sonnet-4-6',
          params: { temperature: 0.3 },
          saved_at: '2026-05-14T12:00:00Z',
          in_catalog: true,
        },
      }),
    } as unknown as Response));

    const documentRef = { cookie: 'csrftoken=abc' } as Document;

    const result = await saveRunnerDefaultModel(
      SAVE_URL,
      {
        initializer_key: 'anthropic',
        model_id: 'claude-sonnet-4-6',
        params: { temperature: 0.3 },
      },
      fetchImpl as unknown as typeof fetch,
      documentRef,
    );

    expect(result.ok).toBe(true);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe(SAVE_URL);
    expect(init?.method).toBe('POST');
    expect((init?.headers as Record<string, string>)['X-CSRFToken']).toBe('abc');
    expect((init?.headers as Record<string, string>)['Content-Type']).toBe(
      'application/json',
    );
    const parsed = JSON.parse(init?.body as string);
    expect(parsed).toEqual({
      initializer_key: 'anthropic',
      model_id: 'claude-sonnet-4-6',
      params: { temperature: 0.3 },
    });
  });

  it('passes the 400 envelope through to the caller', async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: false,
      status: 400,
      json: async () => ({
        error: {
          code: 'model_not_in_catalog',
          message: 'Model anthropic:fake is not in the AvailableLLMModel catalog.',
        },
      }),
    } as unknown as Response));

    const result = await saveRunnerDefaultModel(
      SAVE_URL,
      { initializer_key: 'anthropic', model_id: 'fake', params: {} },
      fetchImpl as unknown as typeof fetch,
      { cookie: '' } as Document,
    );

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.code).toBe('model_not_in_catalog');
      expect(result.status).toBe(400);
    }
  });

  it('synthesizes a network_error envelope when fetch rejects', async () => {
    const fetchImpl = vi.fn(async () => {
      throw new TypeError('Network unreachable');
    });

    const result = await saveRunnerDefaultModel(
      SAVE_URL,
      { initializer_key: 'openai', model_id: 'gpt-4o-mini', params: {} },
      fetchImpl as unknown as typeof fetch,
      { cookie: '' } as Document,
    );

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.code).toBe('network_error');
      expect(result.status).toBe(0);
    }
  });
});

describe('resetRunnerDefaultModel', () => {
  it('issues DELETE on the runner-level URL with the CSRF header', async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ override: null }),
    } as unknown as Response));

    const documentRef = { cookie: 'csrftoken=xyz' } as Document;
    const result = await resetRunnerDefaultModel(
      SAVE_URL,
      fetchImpl as unknown as typeof fetch,
      documentRef,
    );

    expect(result.ok).toBe(true);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe(SAVE_URL);
    expect(init?.method).toBe('DELETE');
    expect((init?.headers as Record<string, string>)['X-CSRFToken']).toBe('xyz');
  });

  it('passes server error envelopes through', async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: false,
      status: 403,
      json: async () => ({
        error: { code: 'forbidden', message: 'not staff' },
      }),
    } as unknown as Response));

    const result = await resetRunnerDefaultModel(
      SAVE_URL,
      fetchImpl as unknown as typeof fetch,
      { cookie: '' } as Document,
    );

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.code).toBe('forbidden');
      expect(result.status).toBe(403);
    }
  });

  it('synthesizes network_error on fetch rejection', async () => {
    const fetchImpl = vi.fn(async () => {
      throw new TypeError('Network unreachable');
    });

    const result = await resetRunnerDefaultModel(
      SAVE_URL,
      fetchImpl as unknown as typeof fetch,
      { cookie: '' } as Document,
    );

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.code).toBe('network_error');
    }
  });
});
