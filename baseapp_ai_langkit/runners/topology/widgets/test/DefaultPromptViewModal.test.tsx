import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { DefaultPromptViewModal } from '../src/DefaultPromptViewModal';
import type { SidebarPrompt } from '../src/types';

const prompt: SidebarPrompt = {
  role: 'usage',
  label: 'Usage prompt',
  prompt: {
    description: 'do the thing',
    required_placeholders: ['{topic}'],
    default_text: 'this is the default text with {topic}',
    override: { text: 'override', saved_at: '2026-05-11T00:00:00Z' },
  },
};

describe('DefaultPromptViewModal', () => {
  it('renders a read-only textarea pre-populated with default_text', () => {
    render(<DefaultPromptViewModal prompt={prompt} onClose={() => {}} />);
    const textarea = screen.getByTestId(
      'rtw-default-modal-textarea',
    ) as HTMLTextAreaElement;
    expect(textarea.value).toBe('this is the default text with {topic}');
    expect(textarea).toHaveAttribute('readonly');
  });

  it('renders the read-only notice', () => {
    render(<DefaultPromptViewModal prompt={prompt} onClose={() => {}} />);
    expect(screen.getByTestId('rtw-default-modal-notice')).toHaveTextContent(
      /read-only/i,
    );
  });

  it('has Close and Copy-to-clipboard buttons (no Save)', () => {
    render(<DefaultPromptViewModal prompt={prompt} onClose={() => {}} />);
    expect(screen.getByTestId('rtw-default-modal-close')).toBeInTheDocument();
    expect(screen.getByTestId('rtw-default-modal-copy')).toBeInTheDocument();
    // No Save button — the shell's default save is replaced by the custom footer.
    expect(screen.queryByTestId('rtw-modal-save')).toBeNull();
  });

  it('omits the Restore button when saveUrl/onRestored are not provided', () => {
    render(<DefaultPromptViewModal prompt={prompt} onClose={() => {}} />);
    expect(screen.queryByTestId('rtw-default-modal-restore')).toBeNull();
  });

  it('renders the Restore button when saveUrl and onRestored are provided', () => {
    render(
      <DefaultPromptViewModal
        prompt={prompt}
        onClose={() => {}}
        saveUrl="/x/topology/nodes/n/usage-prompt/"
        onRestored={() => {}}
      />,
    );
    expect(screen.getByTestId('rtw-default-modal-restore')).toBeInTheDocument();
  });

  it('Close triggers onClose', () => {
    const onClose = vi.fn();
    render(<DefaultPromptViewModal prompt={prompt} onClose={onClose} />);
    fireEvent.click(screen.getByTestId('rtw-default-modal-close'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('Copy writes the default text to the clipboard and flips the label', async () => {
    const writeText = vi.fn(async () => undefined);
    render(
      <DefaultPromptViewModal
        prompt={prompt}
        onClose={() => {}}
        clipboard={{ writeText }}
      />,
    );
    fireEvent.click(screen.getByTestId('rtw-default-modal-copy'));
    await waitFor(() =>
      expect(screen.getByTestId('rtw-default-modal-copy')).toHaveTextContent(
        /copied/i,
      ),
    );
    expect(writeText).toHaveBeenCalledWith('this is the default text with {topic}');
  });

  it('shows a "Copy failed" label when the clipboard rejects', async () => {
    const writeText = vi.fn(async () => {
      throw new Error('denied');
    });
    render(
      <DefaultPromptViewModal
        prompt={prompt}
        onClose={() => {}}
        clipboard={{ writeText }}
      />,
    );
    fireEvent.click(screen.getByTestId('rtw-default-modal-copy'));
    await waitFor(() =>
      expect(screen.getByTestId('rtw-default-modal-copy')).toHaveTextContent(
        /copy failed/i,
      ),
    );
  });
});

describe('DefaultPromptViewModal — Restore default flow', () => {
  const RESTORE_URL = '/x/topology/nodes/n/usage-prompt/';

  function _okFetch(body: unknown = { override: { text: '', saved_at: '2026-05-11' } }) {
    return vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => body,
    } as unknown as Response));
  }

  function _errFetch(status: number, body: unknown) {
    return vi.fn(async () => ({
      ok: false,
      status,
      json: async () => body,
    } as unknown as Response));
  }

  it('asks for confirmation; cancelling does not POST', async () => {
    const onRestored = vi.fn();
    const fetchImpl = _okFetch();
    const confirmImpl = vi.fn(() => false);
    render(
      <DefaultPromptViewModal
        prompt={prompt}
        onClose={() => {}}
        saveUrl={RESTORE_URL}
        onRestored={onRestored}
        fetchImpl={fetchImpl as unknown as typeof fetch}
        documentRef={{ cookie: 'csrftoken=tok' } as Document}
        confirmImpl={confirmImpl}
      />,
    );
    fireEvent.click(screen.getByTestId('rtw-default-modal-restore'));
    expect(confirmImpl).toHaveBeenCalledTimes(1);
    expect(fetchImpl).not.toHaveBeenCalled();
    expect(onRestored).not.toHaveBeenCalled();
  });

  it('on confirm, POSTs empty text and calls onRestored', async () => {
    const onRestored = vi.fn();
    const fetchImpl = _okFetch();
    render(
      <DefaultPromptViewModal
        prompt={prompt}
        onClose={() => {}}
        saveUrl={RESTORE_URL}
        onRestored={onRestored}
        fetchImpl={fetchImpl as unknown as typeof fetch}
        documentRef={{ cookie: 'csrftoken=tok' } as Document}
        confirmImpl={() => true}
      />,
    );
    fireEvent.click(screen.getByTestId('rtw-default-modal-restore'));
    await waitFor(() => expect(onRestored).toHaveBeenCalledTimes(1));
    expect(fetchImpl).toHaveBeenCalledWith(
      RESTORE_URL,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ text: '' }),
      }),
    );
  });

  it('on server error, shows inline error and keeps the modal open', async () => {
    const onRestored = vi.fn();
    const fetchImpl = _errFetch(400, {
      error: { code: 'validation_error', message: 'boom' },
    });
    render(
      <DefaultPromptViewModal
        prompt={prompt}
        onClose={() => {}}
        saveUrl={RESTORE_URL}
        onRestored={onRestored}
        fetchImpl={fetchImpl as unknown as typeof fetch}
        documentRef={{ cookie: 'csrftoken=tok' } as Document}
        confirmImpl={() => true}
      />,
    );
    fireEvent.click(screen.getByTestId('rtw-default-modal-restore'));
    await waitFor(() =>
      expect(
        screen.getByTestId('rtw-default-modal-restore-error'),
      ).toHaveTextContent('boom'),
    );
    expect(onRestored).not.toHaveBeenCalled();
    // Button is back to "Restore default" (not stuck in "Restoring…").
    expect(screen.getByTestId('rtw-default-modal-restore')).toHaveTextContent(
      /restore default/i,
    );
  });

  it('disables Restore (and the other footer buttons) while the request is in flight', () => {
    const onRestored = vi.fn();
    // Never-resolving fetch keeps us in the "restoring" state.
    const fetchImpl = vi.fn(() => new Promise(() => {})) as unknown as typeof fetch;
    render(
      <DefaultPromptViewModal
        prompt={prompt}
        onClose={() => {}}
        saveUrl={RESTORE_URL}
        onRestored={onRestored}
        fetchImpl={fetchImpl}
        documentRef={{ cookie: 'csrftoken=tok' } as Document}
        confirmImpl={() => true}
      />,
    );
    fireEvent.click(screen.getByTestId('rtw-default-modal-restore'));
    expect(screen.getByTestId('rtw-default-modal-restore')).toHaveTextContent(
      /restoring/i,
    );
    expect(screen.getByTestId('rtw-default-modal-restore')).toBeDisabled();
    expect(screen.getByTestId('rtw-default-modal-close')).toBeDisabled();
    expect(screen.getByTestId('rtw-default-modal-copy')).toBeDisabled();
  });
});
