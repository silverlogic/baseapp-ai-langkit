// F03-S01 banner — success path scenarios.
//
// Three states for the tertiary effective-model summary:
//   - override (in_catalog) — "Default model: <label> (<key>) — override"
//   - no override          — "Default model: <label> (<key>) — runner default"
//   - "not declared"       — when default_model_metadata is unset and no override
// Plus the orphan glyph (override exists but in_catalog: false) and the
// empty-catalog disabled Edit button.

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { Banner } from '../src/Banner';
import type {
  AvailableLLMModelRow,
  TopologyRunner,
} from '../src/types';

const CATALOG: AvailableLLMModelRow[] = [
  {
    label: 'GPT-4o mini',
    initializer_key: 'openai',
    model_id: 'gpt-4o-mini',
    default_params: { temperature: 0, max_tokens: 256 },
    allowed_params: ['temperature', 'max_tokens'],
  },
  {
    label: 'Claude Sonnet 4.6',
    initializer_key: 'anthropic',
    model_id: 'claude-sonnet-4-6',
    default_params: { temperature: 0.2, top_p: 0.95 },
    allowed_params: ['temperature', 'top_p'],
  },
];

function runnerBlock(overrides?: Partial<TopologyRunner>): TopologyRunner {
  return {
    label: 'Default chat',
    description: 'Single-node general-purpose chat runner.',
    default_model: {
      initializer_key: 'openai',
      model_id: 'gpt-4o-mini',
      params: { temperature: 0 },
      override: null,
    },
    ...overrides,
  };
}

describe('Banner — success path', () => {
  it('renders label + description + runner-default summary with enabled Edit button', () => {
    render(
      <Banner
        runner={runnerBlock()}
        availableModels={CATALOG}
        onEditRunnerDefault={() => {}}
      />,
    );
    expect(screen.getByTestId('rtw-runner-banner-label').textContent).toBe(
      'Default chat',
    );
    expect(
      screen.getByTestId('rtw-runner-banner-description').textContent,
    ).toMatch(/Single-node general-purpose chat runner/);
    const summary = screen.getByTestId('rtw-runner-banner-summary').textContent ?? '';
    expect(summary).toMatch(/GPT-4o mini/);
    expect(summary).toMatch(/openai/);
    expect(summary).toMatch(/runner default/);
    const editBtn = screen.getByTestId(
      'rtw-runner-banner-edit',
    ) as HTMLButtonElement;
    expect(editBtn.disabled).toBe(false);
  });

  it('omits the description line entirely when description is null', () => {
    render(
      <Banner
        runner={runnerBlock({ description: null })}
        availableModels={CATALOG}
        onEditRunnerDefault={() => {}}
      />,
    );
    expect(screen.queryByTestId('rtw-runner-banner-description')).toBeNull();
  });

  it('preserves whitespace + does NOT process markdown in the description', () => {
    const longDescription = 'First paragraph.\n\nSecond paragraph with **bold** literal.';
    render(
      <Banner
        runner={runnerBlock({ description: longDescription })}
        availableModels={CATALOG}
        onEditRunnerDefault={() => {}}
      />,
    );
    const desc = screen.getByTestId('rtw-runner-banner-description');
    expect(desc.textContent).toBe(longDescription); // verbatim, no transformation
    // The literal asterisks are present, not rendered as <strong>.
    expect(desc.textContent).toContain('**bold**');
  });

  it('shows "— override" suffix when an in-catalog runner-level override exists', () => {
    render(
      <Banner
        runner={runnerBlock({
          default_model: {
            initializer_key: 'openai',
            model_id: 'gpt-4o-mini',
            params: { temperature: 0 },
            override: {
              initializer_key: 'anthropic',
              model_id: 'claude-sonnet-4-6',
              params: { temperature: 0.3 },
              saved_at: '2026-05-14T00:00:00Z',
              in_catalog: true,
            },
          },
        })}
        availableModels={CATALOG}
        onEditRunnerDefault={() => {}}
      />,
    );
    const summarySpan = screen.getByTestId('rtw-runner-banner-summary');
    const summary = summarySpan.textContent ?? '';
    expect(summary).toMatch(/Claude Sonnet 4\.6/);
    expect(summary).toMatch(/anthropic/);
    expect(summary).toMatch(/override/);
    expect(screen.queryByTestId('rtw-runner-banner-orphan-glyph')).toBeNull();
    // Override-active highlight: the summary span SHALL carry the modifier
    // class so admins recognize the active override using the same visual
    // cue as the per-node prompt-pane override (`.rtw-prompt-pane--override`).
    expect(summarySpan.className).toMatch(/rtw-runner-banner__summary--override/);
  });

  it('shows orphan glyph + tooltip when override is out of catalog', () => {
    render(
      <Banner
        runner={runnerBlock({
          default_model: {
            initializer_key: 'openai',
            model_id: 'gpt-4o-mini',
            params: { temperature: 0 },
            override: {
              initializer_key: 'anthropic',
              model_id: 'claude-orphaned',
              params: {},
              saved_at: '2026-05-14T00:00:00Z',
              in_catalog: false,
            },
          },
        })}
        availableModels={CATALOG}
        onEditRunnerDefault={() => {}}
      />,
    );
    const glyph = screen.getByTestId('rtw-runner-banner-orphan-glyph');
    expect(glyph).toBeTruthy();
    expect(glyph.getAttribute('title')).toMatch(/no longer exists/i);
    // Tertiary line still shows the code-declared default.
    const summarySpan = screen.getByTestId('rtw-runner-banner-summary');
    const summary = summarySpan.textContent ?? '';
    expect(summary).toMatch(/GPT-4o mini/);
    expect(summary).toMatch(/runner default/);
    // Orphan path: override-active highlight is NOT applied — the warning
    // glyph carries the signal, and the highlight would visually conflict
    // with the warning treatment.
    expect(summarySpan.className).not.toMatch(/rtw-runner-banner__summary--override/);
  });

  it('shows "Default model: not declared" when code default + override are both missing', () => {
    render(
      <Banner
        runner={runnerBlock({
          default_model: {
            initializer_key: null,
            model_id: null,
            params: {},
            override: null,
          },
        })}
        availableModels={CATALOG}
        onEditRunnerDefault={() => {}}
      />,
    );
    const summarySpan = screen.getByTestId('rtw-runner-banner-summary');
    expect(summarySpan.textContent ?? '').toMatch(/not declared/);
    // No override → no override-active highlight.
    expect(summarySpan.className).not.toMatch(/rtw-runner-banner__summary--override/);
  });
});

describe('Banner — Edit default model button', () => {
  it('fires onEditRunnerDefault on click when catalog is non-empty', () => {
    const onEdit = vi.fn();
    render(
      <Banner
        runner={runnerBlock()}
        availableModels={CATALOG}
        onEditRunnerDefault={onEdit}
      />,
    );
    fireEvent.click(screen.getByTestId('rtw-runner-banner-edit'));
    expect(onEdit).toHaveBeenCalledTimes(1);
  });

  it('is disabled with a tooltip pointing to the catalog admin when catalog is empty', () => {
    const onEdit = vi.fn();
    render(
      <Banner
        runner={runnerBlock()}
        availableModels={[]}
        onEditRunnerDefault={onEdit}
        catalogAdminUrl="/admin/baseapp_ai_langkit_runners/availablellmmodel/"
      />,
    );
    const btn = screen.getByTestId(
      'rtw-runner-banner-edit',
    ) as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
    expect(btn.getAttribute('title')).toMatch(/AvailableLLMModel catalog/);
    fireEvent.click(btn);
    expect(onEdit).not.toHaveBeenCalled();
  });
});
