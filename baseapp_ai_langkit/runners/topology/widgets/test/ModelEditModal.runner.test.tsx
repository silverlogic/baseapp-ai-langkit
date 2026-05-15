// F03-S01 ModelEditModal — target='runner' branch.
//
// Three target-conditional code paths:
//   1. Modal title copy
//   2. Body read-only header copy
//   3. Reset confirm message
// The save URL is passed in by the caller (Root.tsx); the modal itself is
// URL-agnostic. Picker behavior, params discard, error rendering, empty-catalog
// state — all target-agnostic.

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ModelEditModal } from '../src/ModelEditModal';
import type { AvailableLLMModelRow, TopologyModel } from '../src/types';

const CATALOG: AvailableLLMModelRow[] = [
  {
    label: 'GPT-4o mini',
    initializer_key: 'openai',
    model_id: 'gpt-4o-mini',
    // After the per-row params refactor, `allowed_params` mirrors
    // `Object.keys(default_params)` — admins curate which params are tunable
    // per-row on the AvailableLLMModel admin form.
    default_params: { temperature: 0, max_tokens: 256 },
    allowed_params: ['temperature', 'max_tokens'],
  },
];

const RUNNER_DEFAULT_MODEL: TopologyModel = {
  initializer_key: 'openai',
  model_id: 'gpt-4o-mini',
  params: { temperature: 0 },
  override: null,
};

const RUNNER_URL = '/admin/baseapp_ai_langkit_runners/llmrunner/1/topology/default-model/';

function renderRunnerModal(
  props?: Partial<React.ComponentProps<typeof ModelEditModal>>,
) {
  const defaults: React.ComponentProps<typeof ModelEditModal> = {
    target: 'runner',
    model: RUNNER_DEFAULT_MODEL,
    availableModels: CATALOG,
    saveUrl: RUNNER_URL,
    onCancel: vi.fn(),
    onSaved: vi.fn(),
    fetchImpl: vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ override: {} }),
    } as unknown as Response)) as unknown as typeof fetch,
    documentRef: { cookie: 'csrftoken=t' } as Document,
  };
  return render(<ModelEditModal {...defaults} {...props} />);
}

describe('ModelEditModal — target="runner"', () => {
  it('renders the runner-level title copy', () => {
    renderRunnerModal();
    expect(
      screen.getByTestId('rtw-model-modal-title').textContent,
    ).toBe('Edit default model for this runner');
  });

  it('renders the runner-level body header copy ("Code-declared default:")', () => {
    renderRunnerModal();
    const header = screen.getByTestId('rtw-model-modal-default').textContent ?? '';
    expect(header).toMatch(/Code-declared default/);
    expect(header).toMatch(/openai:gpt-4o-mini/);
  });

  it('reset confirm message names the runner-level rung', () => {
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ override: null }),
    } as unknown as Response));
    const confirmSpy = vi.fn(() => false); // user cancels — short-circuit
    renderRunnerModal({
      model: {
        ...RUNNER_DEFAULT_MODEL,
        override: {
          initializer_key: 'openai',
          model_id: 'gpt-4o-mini',
          params: {},
          saved_at: '2026-05-14T00:00:00Z',
          in_catalog: true,
        },
      },
      fetchImpl: fetchImpl as unknown as typeof fetch,
      confirmImpl: confirmSpy,
    });
    fireEvent.click(screen.getByTestId('rtw-model-modal-reset'));
    expect(confirmSpy).toHaveBeenCalledTimes(1);
    expect(confirmSpy.mock.calls[0][0]).toMatch(/runner/i);
    expect(confirmSpy.mock.calls[0][0]).toMatch(/code-declared default/i);
    expect(fetchImpl).not.toHaveBeenCalled(); // user said no
  });

  it('reset confirm + accept hits DELETE on the runner-level URL', async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ override: null }),
    } as unknown as Response));
    const onSaved = vi.fn();
    renderRunnerModal({
      model: {
        ...RUNNER_DEFAULT_MODEL,
        override: {
          initializer_key: 'openai',
          model_id: 'gpt-4o-mini',
          params: {},
          saved_at: '2026-05-14T00:00:00Z',
          in_catalog: true,
        },
      },
      fetchImpl: fetchImpl as unknown as typeof fetch,
      confirmImpl: () => true,
      onSaved,
    });

    fireEvent.click(screen.getByTestId('rtw-model-modal-reset'));
    // Allow the async resetRunnerDefaultModel chain to resolve.
    await Promise.resolve();
    await Promise.resolve();

    expect(fetchImpl).toHaveBeenCalledTimes(1);
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe(RUNNER_URL);
    expect(init?.method).toBe('DELETE');
  });

  it('hides the Reset button when no runner-level override exists', () => {
    renderRunnerModal({
      model: { ...RUNNER_DEFAULT_MODEL, override: null },
    });
    expect(screen.queryByTestId('rtw-model-modal-reset')).toBeNull();
  });
});

describe('ModelEditModal — backward compat (omitting target defaults to "node")', () => {
  it('keeps the per-node title when target prop is omitted', () => {
    render(
      <ModelEditModal
        nodeKey="general_llm"
        model={RUNNER_DEFAULT_MODEL}
        availableModels={CATALOG}
        saveUrl="/topology/nodes/general_llm/model/"
        onCancel={vi.fn()}
        onSaved={vi.fn()}
        fetchImpl={vi.fn(async () => ({
          ok: true,
          status: 200,
          json: async () => ({ override: {} }),
        } as unknown as Response)) as unknown as typeof fetch}
        documentRef={{ cookie: 'csrftoken=t' } as Document}
      />,
    );
    expect(screen.getByTestId('rtw-model-modal-title').textContent).toBe(
      'Model for node general_llm',
    );
    expect(
      screen.getByTestId('rtw-model-modal-default').textContent,
    ).toMatch(/Runner default/);
  });
});
