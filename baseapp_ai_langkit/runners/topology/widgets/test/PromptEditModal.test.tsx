import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { PromptEditModal } from '../src/PromptEditModal';
import type { SidebarPrompt } from '../src/types';

const SAVE_URL = '/admin/x/y/topology/nodes/n/usage-prompt/';
const DOC_WITH_CSRF = { cookie: 'csrftoken=tok' } as Document;

const promptNoOverride: SidebarPrompt = {
  role: 'usage',
  label: 'Usage prompt',
  prompt: {
    description: 'desc',
    // Bare name — codebase convention. The widget checks for the format
    // token `{topic}` in the textarea content (mirroring
    // `BasePromptSchema.validate`).
    required_placeholders: ['topic'],
    default_text: 'default text with {topic}',
    override: null,
  },
};

const promptWithOverride: SidebarPrompt = {
  ...promptNoOverride,
  prompt: {
    ...promptNoOverride.prompt,
    override: { text: 'override text with {topic}', saved_at: '2026-05-11T00:00:00Z' },
  },
};

function _ok(body: unknown) {
  return vi.fn(async () => ({
    ok: true,
    status: 200,
    json: async () => body,
  } as unknown as Response));
}

function _err(status: number, body: unknown) {
  return vi.fn(async () => ({
    ok: false,
    status,
    json: async () => body,
  } as unknown as Response));
}

describe('PromptEditModal', () => {
  it('pre-populates with override.text when present', () => {
    render(
      <PromptEditModal
        prompt={promptWithOverride}
        saveUrl={SAVE_URL}
        onCancel={() => {}}
        onSaved={() => {}}
        documentRef={DOC_WITH_CSRF}
      />,
    );
    const textarea = screen.getByTestId('rtw-modal-textarea') as HTMLTextAreaElement;
    expect(textarea.value).toBe('override text with {topic}');
  });

  it('pre-populates with default_text when no override exists', () => {
    render(
      <PromptEditModal
        prompt={promptNoOverride}
        saveUrl={SAVE_URL}
        onCancel={() => {}}
        onSaved={() => {}}
        documentRef={DOC_WITH_CSRF}
      />,
    );
    const textarea = screen.getByTestId('rtw-modal-textarea') as HTMLTextAreaElement;
    expect(textarea.value).toBe('default text with {topic}');
  });

  it('renders description + required placeholders in the header', () => {
    render(
      <PromptEditModal
        prompt={promptNoOverride}
        saveUrl={SAVE_URL}
        onCancel={() => {}}
        onSaved={() => {}}
        documentRef={DOC_WITH_CSRF}
      />,
    );
    expect(screen.getByTestId('rtw-modal-description')).toHaveTextContent('desc');
    // The placeholder chip in the header shows the bare name.
    expect(screen.getByText('topic')).toBeInTheDocument();
  });

  it('shows a hint when a required placeholder is missing, but keeps Save enabled', () => {
    // The hint is informational — the server is the authoritative validator.
    // Save must remain clickable so the user can trigger the server's
    // structured `missing_placeholders` error and learn what's missing.
    render(
      <PromptEditModal
        prompt={promptNoOverride}
        saveUrl={SAVE_URL}
        onCancel={() => {}}
        onSaved={() => {}}
        documentRef={DOC_WITH_CSRF}
      />,
    );
    const textarea = screen.getByTestId('rtw-modal-textarea') as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'no placeholder here' } });
    // Save stays enabled even though the placeholder is missing.
    expect(screen.getByTestId('rtw-modal-save')).not.toBeDisabled();
    // The hint surfaces the bare name of the missing placeholder.
    expect(screen.getByTestId('rtw-modal-hint')).toHaveTextContent('topic');
    // Once the format token is added, the hint goes away; Save stays enabled.
    fireEvent.change(textarea, { target: { value: 'fine {topic}' } });
    expect(screen.getByTestId('rtw-modal-save')).not.toBeDisabled();
    expect(screen.queryByTestId('rtw-modal-hint')).toBeNull();
  });

  it('treats the bare name as missing — only the full {name} token satisfies the placeholder check', () => {
    // Regression for the bug: typing `{topicXYZ` (or just `topic`) should
    // be flagged as missing because the format-string token isn't complete.
    render(
      <PromptEditModal
        prompt={promptNoOverride}
        saveUrl={SAVE_URL}
        onCancel={() => {}}
        onSaved={() => {}}
        documentRef={DOC_WITH_CSRF}
      />,
    );
    const textarea = screen.getByTestId('rtw-modal-textarea') as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'I mention topic but no braces' } });
    expect(screen.getByTestId('rtw-modal-hint')).toBeInTheDocument();
    fireEvent.change(textarea, { target: { value: 'Truncated {topicXYZ' } });
    expect(screen.getByTestId('rtw-modal-hint')).toBeInTheDocument();
    fireEvent.change(textarea, { target: { value: 'Full token {topic}' } });
    expect(screen.queryByTestId('rtw-modal-hint')).toBeNull();
  });

  it('on success calls onSaved and POSTs the textarea content', async () => {
    const fetchImpl = _ok({ override: { text: 'new {topic}', saved_at: '2026-05-11' } });
    const onSaved = vi.fn();
    render(
      <PromptEditModal
        prompt={promptNoOverride}
        saveUrl={SAVE_URL}
        onCancel={() => {}}
        onSaved={onSaved}
        fetchImpl={fetchImpl as unknown as typeof fetch}
        documentRef={DOC_WITH_CSRF}
      />,
    );
    const textarea = screen.getByTestId('rtw-modal-textarea') as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'new {topic}' } });
    fireEvent.click(screen.getByTestId('rtw-modal-save'));
    await waitFor(() => expect(onSaved).toHaveBeenCalledTimes(1));
    expect(fetchImpl).toHaveBeenCalledWith(
      SAVE_URL,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ text: 'new {topic}' }),
      }),
    );
  });

  it('ESC does not close the edit modal (only Cancel/Save can)', () => {
    const onCancel = vi.fn();
    render(
      <PromptEditModal
        prompt={promptNoOverride}
        saveUrl={SAVE_URL}
        onCancel={onCancel}
        onSaved={() => {}}
        documentRef={DOC_WITH_CSRF}
      />,
    );
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onCancel).not.toHaveBeenCalled();
  });

  it('backdrop click does not close the edit modal (only Cancel/Save can)', () => {
    const onCancel = vi.fn();
    render(
      <PromptEditModal
        prompt={promptNoOverride}
        saveUrl={SAVE_URL}
        onCancel={onCancel}
        onSaved={() => {}}
        documentRef={DOC_WITH_CSRF}
      />,
    );
    fireEvent.click(screen.getByTestId('rtw-modal-backdrop'));
    expect(onCancel).not.toHaveBeenCalled();
  });

  it('Cancel button does close the edit modal', () => {
    const onCancel = vi.fn();
    render(
      <PromptEditModal
        prompt={promptNoOverride}
        saveUrl={SAVE_URL}
        onCancel={onCancel}
        onSaved={() => {}}
        documentRef={DOC_WITH_CSRF}
      />,
    );
    fireEvent.click(screen.getByTestId('rtw-modal-cancel'));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('on missing_placeholders 400 keeps modal open and surfaces missing list', async () => {
    const fetchImpl = _err(400, {
      error: {
        code: 'missing_placeholders',
        message: 'The prompt is missing required placeholders.',
        details: { missing: ['topic'] },
      },
    });
    const onSaved = vi.fn();
    render(
      <PromptEditModal
        prompt={promptNoOverride}
        saveUrl={SAVE_URL}
        onCancel={() => {}}
        onSaved={onSaved}
        fetchImpl={fetchImpl as unknown as typeof fetch}
        documentRef={DOC_WITH_CSRF}
      />,
    );
    // Bypass client check by leaving a value that contains the placeholder
    // (so the client passes), but the server still rejects via the mocked
    // 400. This mirrors the spec's "client mirrors, server is authoritative"
    // contract.
    const textarea = screen.getByTestId('rtw-modal-textarea') as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'fine {topic}' } });
    fireEvent.click(screen.getByTestId('rtw-modal-save'));
    await waitFor(() =>
      expect(screen.getByTestId('rtw-modal-error')).toBeInTheDocument(),
    );
    expect(screen.getByTestId('rtw-modal-error')).toHaveTextContent('topic');
    expect(screen.getByTestId('rtw-modal')).toBeInTheDocument();
    expect(onSaved).not.toHaveBeenCalled();
  });
});
