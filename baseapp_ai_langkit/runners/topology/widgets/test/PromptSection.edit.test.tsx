import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { PromptSection } from '../src/PromptSection';
import type { SidebarPrompt } from '../src/types';

const usagePrompt: SidebarPrompt = {
  role: 'usage',
  label: 'Usage prompt',
  prompt: {
    description: 'do the thing',
    required_placeholders: ['{topic}'],
    default_text: 'default text with {topic}',
    override: null,
  },
};

const usagePromptWithOverride: SidebarPrompt = {
  ...usagePrompt,
  prompt: {
    ...usagePrompt.prompt,
    override: { text: 'override text with {topic}', saved_at: '2026-05-11T00:00:00Z' },
  },
};

describe('PromptSection (edit mode) — F02-S01 affordances', () => {
  it('renders the inline pane CTA when mode is edit and onEditClick is provided', () => {
    render(
      <PromptSection
        mode="edit"
        prompt={usagePrompt}
        onEditClick={() => {}}
      />,
    );
    // No header Edit button — the only affordance is the inline pane CTA
    // ("View / Edit") inside the prompt pane.
    expect(screen.queryByTestId('rtw-edit-usage')).toBeNull();
    expect(
      screen.getByTestId('rtw-view-edit-usage-default'),
    ).toBeInTheDocument();
  });

  it('renders no Edit/View affordance at all when mode is view', () => {
    render(
      <PromptSection
        mode="view"
        prompt={usagePrompt}
        onEditClick={() => {}}
      />,
    );
    expect(screen.queryByTestId('rtw-edit-usage')).toBeNull();
    expect(screen.queryByTestId('rtw-view-edit-usage-default')).toBeNull();
  });

  it('clicking the inline pane CTA calls onEditClick with the prompt', () => {
    const onEditClick = vi.fn();
    render(
      <PromptSection mode="edit" prompt={usagePrompt} onEditClick={onEditClick} />,
    );
    fireEvent.click(screen.getByTestId('rtw-view-edit-usage-default'));
    expect(onEditClick).toHaveBeenCalledTimes(1);
    expect(onEditClick).toHaveBeenCalledWith(usagePrompt);
  });

  it('clicking the clamped default pane (anywhere) opens the same modal', () => {
    const onEditClick = vi.fn();
    render(
      <PromptSection mode="edit" prompt={usagePrompt} onEditClick={onEditClick} />,
    );
    fireEvent.click(screen.getByTestId('rtw-default-usage'));
    expect(onEditClick).toHaveBeenCalledTimes(1);
  });

  it('clicking the inline "View / Edit" button on the clamped pane opens the modal', () => {
    const onEditClick = vi.fn();
    render(
      <PromptSection mode="edit" prompt={usagePrompt} onEditClick={onEditClick} />,
    );
    fireEvent.click(screen.getByTestId('rtw-view-edit-usage-default'));
    expect(onEditClick).toHaveBeenCalledTimes(1);
  });

  it('renders inline action buttons on both panes when an override exists', () => {
    // When an override exists, the default pane's inline CTA fires
    // `onViewDefault` (read-only view), and the override pane's CTA fires
    // `onEditClick`. Both buttons must render; their labels differ.
    render(
      <PromptSection
        mode="edit"
        prompt={usagePromptWithOverride}
        onEditClick={() => {}}
        onViewDefault={() => {}}
      />,
    );
    expect(screen.getByTestId('rtw-view-edit-usage-default')).toBeInTheDocument();
    expect(screen.getByTestId('rtw-view-edit-usage-override')).toBeInTheDocument();
    expect(screen.getByTestId('rtw-view-edit-usage-default')).toHaveTextContent('View');
    expect(screen.getByTestId('rtw-view-edit-usage-override')).toHaveTextContent(
      'View / Edit',
    );
  });

  it('fires onViewDefault (not onEditClick) when clicking the default pane with an override present', () => {
    const onEditClick = vi.fn();
    const onViewDefault = vi.fn();
    render(
      <PromptSection
        mode="edit"
        prompt={usagePromptWithOverride}
        onEditClick={onEditClick}
        onViewDefault={onViewDefault}
      />,
    );
    fireEvent.click(screen.getByTestId('rtw-default-usage'));
    expect(onViewDefault).toHaveBeenCalledTimes(1);
    expect(onEditClick).not.toHaveBeenCalled();
  });

  it('the default pane is non-interactive when override exists but onViewDefault is omitted', () => {
    render(
      <PromptSection
        mode="edit"
        prompt={usagePromptWithOverride}
        onEditClick={() => {}}
      />,
    );
    // No `View` inline button on the default pane because there is no handler
    // to wire it to — clicking the pane would be a no-op, so we don't render
    // the affordance.
    expect(screen.queryByTestId('rtw-view-edit-usage-default')).toBeNull();
  });

  it('keyboard activation (Enter / Space) on the clamped pane opens the modal', () => {
    const onEditClick = vi.fn();
    render(
      <PromptSection mode="edit" prompt={usagePrompt} onEditClick={onEditClick} />,
    );
    fireEvent.keyDown(screen.getByTestId('rtw-default-usage'), { key: 'Enter' });
    expect(onEditClick).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(screen.getByTestId('rtw-default-usage'), { key: ' ' });
    expect(onEditClick).toHaveBeenCalledTimes(2);
  });
});
