import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { mount } from '../src/mount';

describe('mount', () => {
  let warnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    warnSpy.mockRestore();
  });

  it('logs a warning and returns undefined when target is null', () => {
    const result = mount(null, {
      topologyUrl: '/topology/',
      legacyAdminUrl: '/legacy/',
    });
    expect(result).toBeUndefined();
    expect(warnSpy).toHaveBeenCalledTimes(1);
    expect(warnSpy.mock.calls[0]?.[0]).toMatch(/runner-topology-widget/);
  });

  it('does not throw when target is null', () => {
    expect(() =>
      mount(null, { topologyUrl: '/topology/', legacyAdminUrl: '/legacy/' }),
    ).not.toThrow();
  });

  it('exposes window.RunnerTopologyWidget.mount', () => {
    expect(window.RunnerTopologyWidget?.mount).toBe(mount);
  });

  it('renders into the provided element when given a valid target', async () => {
    const target = document.createElement('div');
    document.body.appendChild(target);
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      json: async () => ({ nodes: [], edges: [] }),
    } as unknown as Response));
    const root = mount(target, {
      topologyUrl: '/topology/',
      legacyAdminUrl: '/legacy/',
      fetchImpl: fetchImpl as unknown as typeof fetch,
    });
    expect(root).toBeDefined();
    // Allow effects to flush.
    await new Promise((r) => setTimeout(r, 0));
    expect(target.querySelector('[data-testid="rtw-root"]')).toBeTruthy();
    root?.unmount();
    document.body.removeChild(target);
  });
});
