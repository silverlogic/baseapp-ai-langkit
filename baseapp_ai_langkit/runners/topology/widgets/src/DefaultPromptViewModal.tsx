import { useState } from 'react';

import { EditModalShell } from './EditModalShell';
import { PromptSaveError, savePrompt } from './savePrompt';
import type { SidebarPrompt } from './types';

export interface DefaultPromptViewModalProps {
  prompt: SidebarPrompt;
  onClose: () => void;
  // When provided alongside `onRestored`, render a "Restore default" button
  // that POSTs an empty `text` to the save endpoint. The save handler treats
  // empty text as "no override" (its `clean_*` validators no-op on empty),
  // and the topology read path treats an empty `usage_prompt` / `state_modifier`
  // value as `override: null`. The result, after refresh: override pane gone,
  // default pane is the only thing.
  saveUrl?: string;
  onRestored?: () => void | Promise<void>;
  // Test seams.
  fetchImpl?: typeof fetch;
  documentRef?: Document;
  clipboard?: Pick<Clipboard, 'writeText'>;
  confirmImpl?: (message: string) => boolean;
}

const RESTORE_CONFIRM_MESSAGE =
  'Restore the default prompt? This will remove the current override.';

type RestoreState =
  | { status: 'idle' }
  | { status: 'restoring' }
  | { status: 'error'; error: PromptSaveError };

export function DefaultPromptViewModal({
  prompt,
  onClose,
  saveUrl,
  onRestored,
  fetchImpl,
  documentRef,
  clipboard,
  confirmImpl,
}: DefaultPromptViewModalProps) {
  const [copied, setCopied] = useState<'idle' | 'ok' | 'err'>('idle');
  const [restore, setRestore] = useState<RestoreState>({ status: 'idle' });

  const canRestore = !!saveUrl && !!onRestored;
  const restoring = restore.status === 'restoring';

  const handleCopy = async () => {
    const target =
      clipboard ?? (typeof navigator !== 'undefined' ? navigator.clipboard : null);
    if (!target) {
      setCopied('err');
      return;
    }
    try {
      await target.writeText(prompt.prompt.default_text);
      setCopied('ok');
      window.setTimeout(() => setCopied('idle'), 1800);
    } catch {
      setCopied('err');
    }
  };

  const handleRestore = async () => {
    if (!canRestore || !saveUrl || !onRestored) return;
    const confirmFn =
      confirmImpl ??
      (typeof window !== 'undefined' ? window.confirm.bind(window) : () => false);
    if (!confirmFn(RESTORE_CONFIRM_MESSAGE)) return;
    setRestore({ status: 'restoring' });
    const result = await savePrompt(
      saveUrl,
      '',
      fetchImpl ?? window.fetch,
      documentRef ?? document,
    );
    if (result.ok) {
      // Parent re-fetches the topology and closes the modal.
      await onRestored();
      return;
    }
    setRestore({ status: 'error', error: result.error });
  };

  return (
    <EditModalShell
      isOpen
      onCancel={restoring ? () => undefined : onClose}
      dirty={false}
      header={
        <>
          <h3 className="rtw-modal__title" data-testid="rtw-default-modal-title">
            Default {prompt.label.toLowerCase()}
          </h3>
          <p
            className="rtw-modal__description"
            data-testid="rtw-default-modal-description"
          >
            {prompt.prompt.description}
          </p>
          <div className="rtw-modal__notice" data-testid="rtw-default-modal-notice">
            Read-only — this is the in-code default. To change the prompt, edit the
            override.
          </div>
        </>
      }
      body={
        <>
          <textarea
            className="rtw-modal__textarea rtw-modal__textarea--readonly"
            data-testid="rtw-default-modal-textarea"
            value={prompt.prompt.default_text}
            readOnly
            aria-label={`Default ${prompt.label.toLowerCase()} (read-only)`}
          />
          {restore.status === 'error' && (
            <div
              className="rtw-modal__error"
              data-testid="rtw-default-modal-restore-error"
            >
              {restore.error.message}
            </div>
          )}
        </>
      }
      footer={
        <>
          <div className="rtw-modal__footer-left">
            {canRestore && (
              <button
                type="button"
                className="rtw-modal__btn rtw-modal__btn--danger"
                data-testid="rtw-default-modal-restore"
                onClick={handleRestore}
                disabled={restoring}
                aria-label="Restore default prompt"
              >
                {restoring ? 'Restoring…' : 'Restore default'}
              </button>
            )}
          </div>
          <div className="rtw-modal__footer-right">
            <button
              type="button"
              className="rtw-modal__btn"
              data-testid="rtw-default-modal-close"
              onClick={onClose}
              disabled={restoring}
            >
              Close
            </button>
            <button
              type="button"
              className="rtw-modal__btn rtw-modal__btn--primary"
              data-testid="rtw-default-modal-copy"
              onClick={handleCopy}
              disabled={restoring}
            >
              {copied === 'ok'
                ? 'Copied!'
                : copied === 'err'
                  ? 'Copy failed'
                  : 'Copy to clipboard'}
            </button>
          </div>
        </>
      }
    />
  );
}
