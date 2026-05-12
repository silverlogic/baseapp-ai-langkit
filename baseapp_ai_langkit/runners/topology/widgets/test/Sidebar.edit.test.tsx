import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { Sidebar } from '../src/Sidebar';
import type { GraphNodeData } from '../src/layout';

const node: GraphNodeData = {
  key: 'general_llm',
  class_name: 'MessagesWorker',
  kind: 'worker',
  model: { identifier: 'gpt-4o-mini' },
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

  it('renders no Edit affordance on the model pane (model pane has no Edit in S01)', () => {
    render(
      <Sidebar
        node={node}
        onClose={() => {}}
        promptMode="edit"
        onEditPrompt={() => {}}
      />,
    );
    // Model is rendered as a meta line, not as an interactive pane.
    expect(screen.getByText(/model: gpt-4o-mini/)).toBeInTheDocument();
    // No header Edit button and no inline pane CTA for the model.
    expect(screen.queryByTestId('rtw-edit-model')).toBeNull();
    expect(screen.queryByTestId('rtw-view-edit-model-default')).toBeNull();
    expect(screen.queryByTestId('rtw-view-edit-model-override')).toBeNull();
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
