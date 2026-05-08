import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Root, fetchTopology } from '../src/Root';
import type { TopologyResponse } from '../src/types';

function makeFetch(response: Partial<Response> & { jsonBody?: unknown }) {
  return vi.fn(async () => {
    const r = response;
    return {
      ok: r.ok ?? true,
      status: r.status ?? 200,
      json: async () => r.jsonBody,
    } as unknown as Response;
  });
}

describe('Root error branches', () => {
  const errorCodes = [
    'runner_unregistered',
    'topology_builder_not_declared',
    'workflow_init_failed',
    'unknown',
  ] as const;

  for (const code of errorCodes) {
    it(`renders the error banner with the legacy CTA for code "${code}"`, async () => {
      const payload: TopologyResponse = {
        nodes: [],
        edges: [],
        error: { code, message: `kaboom: ${code}` },
      };
      const fetchImpl = makeFetch({ ok: true, jsonBody: payload });
      render(
        <Root
          topologyUrl="/admin/topology/"
          legacyAdminUrl="/admin/legacy/"
          fetchImpl={fetchImpl as unknown as typeof fetch}
        />,
      );
      await waitFor(() =>
        expect(screen.getByTestId('rtw-error-banner')).toBeInTheDocument(),
      );
      expect(screen.getByText(`kaboom: ${code}`)).toBeInTheDocument();
      const cta = screen.getByText(/Edit prompts in the legacy admin/);
      expect(cta).toHaveAttribute('href', '/admin/legacy/');
    });
  }

  it('falls back to the error banner on network failure', async () => {
    const fetchImpl = vi.fn(async () => {
      throw new Error('network down');
    });
    render(
      <Root
        topologyUrl="/admin/topology/"
        legacyAdminUrl="/admin/legacy/"
        fetchImpl={fetchImpl as unknown as typeof fetch}
      />,
    );
    await waitFor(() =>
      expect(screen.getByTestId('rtw-error-banner')).toBeInTheDocument(),
    );
    const cta = screen.getByText(/Edit prompts in the legacy admin/);
    expect(cta).toHaveAttribute('href', '/admin/legacy/');
  });

  it('falls back to the error banner on non-2xx response', async () => {
    const fetchImpl = makeFetch({ ok: false, status: 500 });
    render(
      <Root
        topologyUrl="/admin/topology/"
        legacyAdminUrl="/admin/legacy/"
        fetchImpl={fetchImpl as unknown as typeof fetch}
      />,
    );
    await waitFor(() =>
      expect(screen.getByTestId('rtw-error-banner')).toBeInTheDocument(),
    );
  });
});

describe('Root happy path', () => {
  it('renders the empty-canvas message when topology has zero nodes (no error)', async () => {
    const payload: TopologyResponse = { nodes: [], edges: [] };
    const fetchImpl = makeFetch({ ok: true, jsonBody: payload });
    render(
      <Root
        topologyUrl="/admin/topology/"
        legacyAdminUrl="/admin/legacy/"
        fetchImpl={fetchImpl as unknown as typeof fetch}
      />,
    );
    await waitFor(() =>
      expect(screen.getByTestId('rtw-empty')).toBeInTheDocument(),
    );
    expect(screen.queryByTestId('rtw-error-banner')).toBeNull();
  });
});

describe('fetchTopology', () => {
  it('uses same-origin credentials and accepts JSON', async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      json: async () => ({ nodes: [], edges: [] }),
    } as unknown as Response));
    await fetchTopology('/topology/', fetchImpl as unknown as typeof fetch);
    expect(fetchImpl).toHaveBeenCalledWith(
      '/topology/',
      expect.objectContaining({
        credentials: 'same-origin',
        headers: expect.objectContaining({ Accept: 'application/json' }),
      }),
    );
  });

  it('does not send a CSRF token header', async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      json: async () => ({ nodes: [], edges: [] }),
    } as unknown as Response));
    await fetchTopology('/topology/', fetchImpl as unknown as typeof fetch);
    const init = (fetchImpl.mock.calls[0]?.[1] ?? {}) as RequestInit;
    const headers = (init.headers ?? {}) as Record<string, string>;
    expect(Object.keys(headers).map((k) => k.toLowerCase())).not.toContain(
      'x-csrftoken',
    );
  });

  it('synthesizes an unknown error on non-JSON body', async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      json: async () => {
        throw new Error('bad json');
      },
    } as unknown as Response));
    const result = await fetchTopology(
      '/topology/',
      fetchImpl as unknown as typeof fetch,
    );
    expect('code' in result && result.code === 'unknown').toBe(true);
  });
});
