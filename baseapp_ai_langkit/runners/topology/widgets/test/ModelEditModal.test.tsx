import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ModelEditModal } from '../src/ModelEditModal';
import type { AvailableLLMModelRow, TopologyModel } from '../src/types';

const CATALOG: AvailableLLMModelRow[] = [
  {
    label: 'GPT-4o mini',
    initializer_key: 'openai',
    model_id: 'gpt-4o-mini',
    default_params: { temperature: 0 },
    allowed_params: ['temperature', 'max_tokens', 'top_p'],
  },
  {
    label: 'Claude Sonnet 4.6',
    initializer_key: 'anthropic',
    model_id: 'claude-sonnet-4-6',
    default_params: {},
    allowed_params: ['temperature', 'top_p'],
  },
];

const DEFAULT_MODEL: TopologyModel = {
  initializer_key: 'openai',
  model_id: 'gpt-4o-mini',
  params: { temperature: 0 },
  override: null,
};

const SAVE_URL = '/topology/nodes/general_llm/model/';

function renderModal(props?: Partial<React.ComponentProps<typeof ModelEditModal>>) {
  const defaults: React.ComponentProps<typeof ModelEditModal> = {
    nodeKey: 'general_llm',
    model: DEFAULT_MODEL,
    availableModels: CATALOG,
    saveUrl: SAVE_URL,
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

describe('ModelEditModal', () => {
  it('opens with default selection matching the runner default', () => {
    renderModal();
    const picker = screen.getByTestId('rtw-model-modal-picker') as HTMLSelectElement;
    expect(picker.value).toBe('openai:gpt-4o-mini');
  });

  it('renders params for the picked initializer (OpenAI → 3 controls)', () => {
    renderModal();
    expect(screen.getByTestId('rtw-model-modal-param-temperature')).toBeInTheDocument();
    expect(screen.getByTestId('rtw-model-modal-param-max_tokens')).toBeInTheDocument();
    expect(screen.getByTestId('rtw-model-modal-param-top_p')).toBeInTheDocument();
  });

  it('renders help text under temperature/max_tokens/top_p', () => {
    renderModal();
    expect(
      screen.getByTestId('rtw-model-modal-param-help-temperature').textContent,
    ).toMatch(/0\.0[–-]2\.0/);
    expect(
      screen.getByTestId('rtw-model-modal-param-help-max_tokens').textContent,
    ).toMatch(/positive integer/i);
    expect(
      screen.getByTestId('rtw-model-modal-param-help-top_p').textContent,
    ).toMatch(/nucleus sampling/i);
  });

  it('re-renders params and discards old-key values when picker changes (OpenAI → Anthropic)', async () => {
    renderModal();
    // Set max_tokens under OpenAI.
    const maxTokensInput = screen
      .getByTestId('rtw-model-modal-param-max_tokens')
      .querySelector('input') as HTMLInputElement;
    fireEvent.change(maxTokensInput, { target: { value: '256' } });
    expect(maxTokensInput.value).toBe('256');

    // Switch to Anthropic — Anthropic's allowed_params here is temperature + top_p, no max_tokens.
    fireEvent.change(screen.getByTestId('rtw-model-modal-picker'), {
      target: { value: 'anthropic:claude-sonnet-4-6' },
    });

    await waitFor(() => {
      expect(screen.queryByTestId('rtw-model-modal-param-max_tokens')).toBeNull();
    });
    expect(screen.getByTestId('rtw-model-modal-param-temperature')).toBeInTheDocument();
    expect(screen.getByTestId('rtw-model-modal-param-top_p')).toBeInTheDocument();
  });

  it('renders an orphan warning when the override is out of catalog', () => {
    const orphanModel: TopologyModel = {
      ...DEFAULT_MODEL,
      override: {
        initializer_key: 'anthropic',
        model_id: 'claude-not-in-catalog',
        params: { temperature: 0.2 },
        saved_at: '2026-05-12T12:00:00Z',
        in_catalog: false,
      },
    };
    renderModal({ model: orphanModel });
    expect(screen.getByTestId('rtw-model-modal-orphan-warning')).toBeInTheDocument();
    // The picker falls back to the runner default (which IS in catalog).
    const picker = screen.getByTestId('rtw-model-modal-picker') as HTMLSelectElement;
    expect(picker.value).toBe('openai:gpt-4o-mini');
  });

  it('renders empty-catalog state when availableModels is empty', () => {
    renderModal({ availableModels: [] });
    expect(screen.getByTestId('rtw-model-modal-empty')).toBeInTheDocument();
    // Save button is disabled (no selected row).
    const saveBtn = screen.getByTestId('rtw-modal-save') as HTMLButtonElement;
    expect(saveBtn.disabled).toBe(true);
  });

  it('disables Save while an inline param error is present', () => {
    renderModal();
    const tempInput = screen
      .getByTestId('rtw-model-modal-param-temperature')
      .querySelector('input') as HTMLInputElement;
    fireEvent.change(tempInput, { target: { value: '5' } }); // > 2 → out of range
    const saveBtn = screen.getByTestId('rtw-modal-save') as HTMLButtonElement;
    expect(saveBtn.disabled).toBe(true);
    expect(
      screen.getByTestId('rtw-model-modal-param-error-temperature'),
    ).toBeInTheDocument();
  });

  it('POSTs and calls onSaved on a 200 response', async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        override: {
          initializer_key: 'openai',
          model_id: 'gpt-4o-mini',
          params: { temperature: 0.4 },
          saved_at: '2026-05-12T12:00:00Z',
          in_catalog: true,
        },
      }),
    } as unknown as Response));
    const onSaved = vi.fn();
    renderModal({ fetchImpl: fetchImpl as unknown as typeof fetch, onSaved });

    const tempInput = screen
      .getByTestId('rtw-model-modal-param-temperature')
      .querySelector('input') as HTMLInputElement;
    fireEvent.change(tempInput, { target: { value: '0.4' } });
    fireEvent.click(screen.getByTestId('rtw-modal-save'));

    await waitFor(() => expect(onSaved).toHaveBeenCalledTimes(1));
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    const [, init] = fetchImpl.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({
      initializer_key: 'openai',
      model_id: 'gpt-4o-mini',
      params: { temperature: 0.4 },
    });
  });

  it('surfaces a server error envelope inline on a 400 response', async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: false,
      status: 400,
      json: async () => ({
        error: {
          code: 'param_invalid',
          message: 'Out of range.',
          details: { invalid: ['temperature'] },
        },
      }),
    } as unknown as Response));
    renderModal({ fetchImpl: fetchImpl as unknown as typeof fetch });
    fireEvent.click(screen.getByTestId('rtw-modal-save'));
    await waitFor(() =>
      expect(screen.getByTestId('rtw-model-modal-error')).toBeInTheDocument(),
    );
    expect(screen.getByTestId('rtw-model-modal-error').textContent).toMatch(/Out of range/);
    expect(screen.getByTestId('rtw-model-modal-error').textContent).toMatch(/temperature/);
  });

  it('calls onCancel via the shell footer Cancel button', () => {
    const onCancel = vi.fn();
    renderModal({ onCancel });
    fireEvent.click(screen.getByTestId('rtw-modal-cancel'));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  describe('Reset to default', () => {
    const overrideModel: TopologyModel = {
      ...DEFAULT_MODEL,
      override: {
        initializer_key: 'openai',
        model_id: 'gpt-4o-mini',
        params: { temperature: 0.5 },
        saved_at: '2026-05-12T12:00:00Z',
        in_catalog: true,
      },
    };

    it('does not render the Reset button when there is no override', () => {
      renderModal({ model: DEFAULT_MODEL });
      expect(screen.queryByTestId('rtw-model-modal-reset')).toBeNull();
    });

    it('renders the Reset button when an override exists', () => {
      renderModal({ model: overrideModel });
      expect(screen.getByTestId('rtw-model-modal-reset')).toBeInTheDocument();
    });

    it('skips the DELETE call when the confirm prompt is dismissed', () => {
      const fetchImpl = vi.fn();
      renderModal({
        model: overrideModel,
        fetchImpl: fetchImpl as unknown as typeof fetch,
        confirmImpl: () => false,
      });
      fireEvent.click(screen.getByTestId('rtw-model-modal-reset'));
      expect(fetchImpl).not.toHaveBeenCalled();
    });

    it('DELETEs the override and calls onSaved on confirm', async () => {
      const fetchImpl = vi.fn(async () => ({
        ok: true,
        status: 200,
        json: async () => ({ override: null }),
      } as unknown as Response));
      const onSaved = vi.fn();
      renderModal({
        model: overrideModel,
        fetchImpl: fetchImpl as unknown as typeof fetch,
        confirmImpl: () => true,
        onSaved,
      });
      fireEvent.click(screen.getByTestId('rtw-model-modal-reset'));
      await waitFor(() => expect(onSaved).toHaveBeenCalledTimes(1));
      expect(fetchImpl).toHaveBeenCalledTimes(1);
      const [, init] = fetchImpl.mock.calls[0] as [string, RequestInit];
      expect(init.method).toBe('DELETE');
    });

    it('surfaces a server error inline if the DELETE fails', async () => {
      const fetchImpl = vi.fn(async () => ({
        ok: false,
        status: 404,
        json: async () => ({
          error: { code: 'node_unknown', message: 'Node missing.' },
        }),
      } as unknown as Response));
      renderModal({
        model: overrideModel,
        fetchImpl: fetchImpl as unknown as typeof fetch,
        confirmImpl: () => true,
      });
      fireEvent.click(screen.getByTestId('rtw-model-modal-reset'));
      await waitFor(() =>
        expect(screen.getByTestId('rtw-model-modal-error')).toBeInTheDocument(),
      );
      expect(screen.getByTestId('rtw-model-modal-error').textContent).toMatch(
        /Node missing/,
      );
    });
  });
});
