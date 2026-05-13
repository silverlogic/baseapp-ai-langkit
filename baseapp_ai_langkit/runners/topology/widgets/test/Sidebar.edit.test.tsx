import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { Sidebar } from '../src/Sidebar';
import type { GraphNodeData } from '../src/layout';

const node: GraphNodeData = {
  key: 'general_llm',
  class_name: 'MessagesWorker',
  kind: 'worker',
  model: {
    initializer_key: 'openai',
    model_id: 'gpt-4o-mini',
    params: {},
    override: null,
  },
  has_override: false,
  prompts: [
    {
      role: 'usage',
      label: 'Usage prompt',
      prompt: {
        description: 'desc-u',
        required_placeholders: [],
        default_text: 'u-default',
      },
    },
    {
      role: 'state_modifier',
      label: 'State modifier — 0',
      prompt: {
        description: 'desc-sm',
        required_placeholders: [],
        default_text: 's-default',
      },
      state_modifier_key: '0',
    },
  ],
};

describe('Sidebar (edit mode) — F02-S01 affordances', () => {
  it('renders inline pane CTAs on every prompt pane in edit mode', () => {
    render(
      <Sidebar
        node={node}
        onClose={() => {}}
        promptMode="edit"
        onEditPrompt={() => {}}
      />,
    );
    // Header Edit buttons are gone — the inline pane CTAs are the only
    // affordance.
    expect(screen.queryByTestId('rtw-edit-usage')).toBeNull();
    expect(screen.queryByTestId('rtw-edit-state_modifier')).toBeNull();
    expect(
      screen.getByTestId('rtw-view-edit-usage-default'),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId('rtw-view-edit-state_modifier-default'),
    ).toBeInTheDocument();
  });

  it('renders an Edit affordance on the model pane in edit mode (F02-S02)', () => {
    render(
      <Sidebar
        node={node}
        onClose={() => {}}
        promptMode="edit"
        onEditPrompt={() => {}}
        onEditModel={() => {}}
      />,
    );
    // Model is rendered as its own section with a default pane carrying an
    // inline View / Edit affordance (S02 reverses S01's "no edit on model").
    const modelSection = screen.getByTestId('rtw-model-section');
    expect(modelSection.textContent).toMatch(/openai:gpt-4o-mini/);
    expect(
      screen.getByTestId('rtw-view-edit-model-default'),
    ).toBeInTheDocument();
  });

  it('renders no model Edit affordance when onEditModel is not provided (view-only)', () => {
    render(
      <Sidebar
        node={node}
        onClose={() => {}}
        promptMode="edit"
        onEditPrompt={() => {}}
      />,
    );
    // Edit prop omitted → the inline CTA does not render even in edit mode.
    expect(screen.queryByTestId('rtw-view-edit-model-default')).toBeNull();
    expect(screen.queryByTestId('rtw-view-edit-model-override')).toBeNull();
  });

  it('clicking the model pane CTA calls onEditModel', () => {
    const onEditModel = vi.fn();
    render(
      <Sidebar
        node={node}
        onClose={() => {}}
        promptMode="edit"
        onEditPrompt={() => {}}
        onEditModel={onEditModel}
      />,
    );
    fireEvent.click(screen.getByTestId('rtw-view-edit-model-default'));
    expect(onEditModel).toHaveBeenCalledTimes(1);
  });

  it('clicking the inline state-modifier CTA calls onEditPrompt with that prompt', () => {
    const onEditPrompt = vi.fn();
    render(
      <Sidebar
        node={node}
        onClose={() => {}}
        promptMode="edit"
        onEditPrompt={onEditPrompt}
      />,
    );
    fireEvent.click(
      screen.getByTestId('rtw-view-edit-state_modifier-default'),
    );
    expect(onEditPrompt).toHaveBeenCalledTimes(1);
    expect(onEditPrompt.mock.calls[0]?.[0]?.role).toBe('state_modifier');
    expect(onEditPrompt.mock.calls[0]?.[0]?.state_modifier_key).toBe('0');
  });
});
