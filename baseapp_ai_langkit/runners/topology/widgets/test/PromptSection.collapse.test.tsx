import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { PromptSection } from '../src/PromptSection';
import type { SidebarPrompt } from '../src/types';

const withOverride: SidebarPrompt = {
  role: 'usage',
  label: 'Usage prompt',
  prompt: {
    description: 'do the thing',
    required_placeholders: [],
    default_text: 'default body text',
    override: { text: 'override body text', saved_at: '2026-05-11T00:00:00Z' },
  },
};

const noOverride: SidebarPrompt = {
  role: 'usage',
  label: 'Usage prompt',
  prompt: {
    description: 'do the thing',
    required_placeholders: [],
    default_text: 'default body text',
    override: null,
  },
};

describe('PromptSection collapse behavior', () => {
  it('renders the default dropdown above the override pane when an override exists', () => {
    // Smoke-test feedback: default toggle goes on top, override below.
    render(<PromptSection mode="view" prompt={withOverride} />);
    const toggle = screen.getByTestId('rtw-toggle-default-usage');
    const override = screen.getByTestId('rtw-override-usage');
    expect(
      toggle.compareDocumentPosition(override) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it('hides the default pane behind a "See default" toggle when override exists', () => {
    render(<PromptSection mode="view" prompt={withOverride} />);
    const toggle = screen.getByTestId('rtw-toggle-default-usage');
    expect(toggle).toHaveTextContent(/see default/i);
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    // The collapsible wrapper is hidden by default.
    expect(screen.getByTestId('rtw-collapsible-default-usage')).toHaveAttribute(
      'hidden',
    );
  });

  it('clicking "See default" reveals the default pane and flips the label', () => {
    render(<PromptSection mode="view" prompt={withOverride} />);
    const toggle = screen.getByTestId('rtw-toggle-default-usage');
    fireEvent.click(toggle);
    expect(toggle).toHaveTextContent(/hide default/i);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(
      screen.getByTestId('rtw-collapsible-default-usage'),
    ).not.toHaveAttribute('hidden');
  });

  it('does not render the toggle when no override exists (default pane is the only thing)', () => {
    render(<PromptSection mode="view" prompt={noOverride} />);
    expect(screen.queryByTestId('rtw-toggle-default-usage')).toBeNull();
    // Default pane still renders, just unwrapped.
    expect(screen.getByTestId('rtw-default-usage')).toBeInTheDocument();
  });
});
