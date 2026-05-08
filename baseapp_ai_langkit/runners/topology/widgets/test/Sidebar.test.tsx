import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Sidebar } from '../src/Sidebar';
import type { GraphNodeData } from '../src/layout';

const baseNode: GraphNodeData = {
  key: 'agent_a',
  class_name: 'AgentA',
  kind: 'agent',
  model: { identifier: 'gpt-4o' },
  prompts: [],
};

const nodeWithBothPrompts: GraphNodeData = {
  ...baseNode,
  prompts: [
    {
      role: 'usage',
      label: 'Usage prompt',
      prompt: {
        description: 'u-desc',
        required_placeholders: [],
        default_text: 'u-default',
      },
    },
    {
      role: 'state_modifier',
      label: 'State modifier — shape',
      prompt: {
        description: 's-desc',
        required_placeholders: [],
        default_text: 's-default',
      },
    },
  ],
};

describe('Sidebar', () => {
  it('shows identity, kind, and model in the header', () => {
    render(<Sidebar node={baseNode} onClose={() => {}} />);
    expect(screen.getByText('agent_a')).toBeInTheDocument();
    expect(screen.getByText('AgentA')).toBeInTheDocument();
    expect(screen.getByText(/kind: agent/)).toBeInTheDocument();
    expect(screen.getByText(/model: gpt-4o/)).toBeInTheDocument();
  });

  it('renders no prompt sections when the node has no prompts', () => {
    render(<Sidebar node={baseNode} onClose={() => {}} />);
    expect(screen.queryByTestId('rtw-prompt-usage')).toBeNull();
    expect(screen.queryByTestId('rtw-prompt-state_modifier')).toBeNull();
  });

  it('renders both usage and state-modifier prompts using the same shape', () => {
    render(<Sidebar node={nodeWithBothPrompts} onClose={() => {}} />);
    expect(screen.getByTestId('rtw-prompt-usage')).toBeInTheDocument();
    expect(screen.getByTestId('rtw-prompt-state_modifier')).toBeInTheDocument();
    expect(screen.getByTestId('rtw-default-usage')).toBeInTheDocument();
    expect(screen.getByTestId('rtw-default-state_modifier')).toBeInTheDocument();
  });

  it('contains no Edit or Save affordance anywhere', () => {
    render(<Sidebar node={nodeWithBothPrompts} onClose={() => {}} />);
    expect(screen.queryByRole('button', { name: /edit/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /save/i })).toBeNull();
    expect(document.querySelector('form')).toBeNull();
    expect(document.querySelector('input')).toBeNull();
    expect(document.querySelector('textarea')).toBeNull();
  });

  it('calls onClose when the close button is clicked', () => {
    const onClose = vi.fn();
    render(<Sidebar node={baseNode} onClose={onClose} />);
    fireEvent.click(screen.getByRole('button', { name: /close/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('calls onClose when Escape is pressed', () => {
    const onClose = vi.fn();
    render(<Sidebar node={baseNode} onClose={onClose} />);
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
