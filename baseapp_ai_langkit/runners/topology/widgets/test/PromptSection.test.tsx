import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { PromptSection } from '../src/PromptSection';
import type { SidebarPrompt } from '../src/types';

const usagePromptNoOverride: SidebarPrompt = {
  role: 'usage',
  label: 'Usage prompt',
  prompt: {
    description: 'do the thing',
    required_placeholders: ['{input}', '{context}'],
    default_text: 'You are a helpful agent.',
    override: null,
  },
};

const usagePromptWithOverride: SidebarPrompt = {
  ...usagePromptNoOverride,
  prompt: {
    ...usagePromptNoOverride.prompt,
    override: { text: 'Custom override text', saved_at: '2026-05-08T12:00:00Z' },
  },
};

const stateModifierPrompt: SidebarPrompt = {
  role: 'state_modifier',
  label: 'State modifier — shape_user_input',
  prompt: {
    description: 'reshape inputs',
    required_placeholders: [],
    default_text: 'sm default',
    override: null,
  },
};

describe('PromptSection', () => {
  it('renders default text only when no override exists', () => {
    render(<PromptSection mode="view" prompt={usagePromptNoOverride} />);
    expect(screen.getByText('Usage prompt')).toBeInTheDocument();
    expect(screen.getByText('do the thing')).toBeInTheDocument();
    expect(screen.getByTestId('rtw-default-usage')).toBeInTheDocument();
    expect(screen.queryByTestId('rtw-override-usage')).toBeNull();
  });

  it('renders default and override side by side when override exists', () => {
    render(<PromptSection mode="view" prompt={usagePromptWithOverride} />);
    expect(screen.getByTestId('rtw-default-usage')).toBeInTheDocument();
    expect(screen.getByTestId('rtw-override-usage')).toBeInTheDocument();
    expect(screen.getByText('Custom override text')).toBeInTheDocument();
    expect(screen.getByText(/2026-05-08/)).toBeInTheDocument();
  });

  it('renders required placeholders as chips', () => {
    render(<PromptSection mode="view" prompt={usagePromptNoOverride} />);
    expect(screen.getByText('{input}')).toBeInTheDocument();
    expect(screen.getByText('{context}')).toBeInTheDocument();
  });

  it('uses the same shape for state-modifier prompts', () => {
    render(<PromptSection mode="view" prompt={stateModifierPrompt} />);
    expect(screen.getByTestId('rtw-prompt-state_modifier')).toBeInTheDocument();
    expect(screen.getByText('State modifier — shape_user_input')).toBeInTheDocument();
    expect(screen.getByTestId('rtw-default-state_modifier')).toBeInTheDocument();
  });

  it('contains no editable input or save affordance', () => {
    render(<PromptSection mode="view" prompt={usagePromptWithOverride} />);
    expect(document.querySelector('input')).toBeNull();
    expect(document.querySelector('textarea')).toBeNull();
    expect(document.querySelector('form')).toBeNull();
    expect(screen.queryByRole('button', { name: /save/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /submit/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /edit/i })).toBeNull();
  });
});
