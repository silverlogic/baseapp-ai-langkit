import React, { useEffect, useRef } from 'react';

// Reusable almost-full-width edit modal chrome.
//
// Body and header are slots; the shell owns ESC-to-cancel, click-outside
// dismissal, focus-trap on first render, and the Save/Cancel footer with
// disabled-state coordination. F02-S01 ships this shell so F02-S02's model
// editor can plug in its own body and inherit the chrome verbatim.

export interface EditModalShellProps {
  isOpen: boolean;
  onCancel: () => void;
  // Optional when `footer` is provided — view-only modals don't have a save.
  onSave?: () => void;
  saveDisabled?: boolean;
  saving?: boolean;
  header: React.ReactNode;
  body: React.ReactNode;
  saveLabel?: string;
  cancelLabel?: string;
  // When provided, replaces the default Save/Cancel footer entirely.
  // Use this for view-only modals (e.g., DefaultPromptViewModal) that need
  // custom actions like "Copy to clipboard" + "Close".
  footer?: React.ReactNode;
  // When the user has unsaved changes, the shell asks to confirm before
  // dismissing via ESC or click-outside. Defaults to false — the body owns
  // dirty tracking.
  dirty?: boolean;
  // When true, ESC and backdrop-click are no-ops; the only way out is the
  // Cancel button (or whatever the custom footer wires). Use for edit
  // modals where accidental dismissal would discard typed content.
  disableOutsideDismiss?: boolean;
  // 'wide' (default, 95vw) for multi-paragraph prompt editing; 'compact'
  // (~600px max) for short forms like the model edit modal.
  size?: 'wide' | 'compact';
  // Optional left-anchored footer slot — rendered to the left of the
  // Cancel/Save buttons. Used by ModelEditModal for the "Reset to default"
  // affordance. Ignored when `footer` (full custom footer) is provided.
  footerLeft?: React.ReactNode;
}

export function EditModalShell({
  isOpen,
  onCancel,
  onSave,
  saveDisabled = false,
  saving = false,
  header,
  body,
  saveLabel = 'Save',
  cancelLabel = 'Cancel',
  footer,
  dirty = false,
  disableOutsideDismiss = false,
  size = 'wide',
  footerLeft,
}: EditModalShellProps) {
  const modalRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      e.stopPropagation();
      if (disableOutsideDismiss) return;
      _attemptCancel(dirty, onCancel);
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [isOpen, dirty, onCancel, disableOutsideDismiss]);

  useEffect(() => {
    if (!isOpen) return;
    // Focus-trap: when the modal opens, focus the first focusable child so
    // keyboard nav starts inside the modal.
    const root = modalRef.current;
    if (!root) return;
    const focusable = root.querySelector<HTMLElement>(
      'textarea, input, select, [role="button"], button:not([disabled])',
    );
    focusable?.focus();
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div
      className="rtw-modal-backdrop"
      data-testid="rtw-modal-backdrop"
      onClick={(e) => {
        if (disableOutsideDismiss) return;
        if (e.target === e.currentTarget) _attemptCancel(dirty, onCancel);
      }}
    >
      <div
        ref={modalRef}
        className={'rtw-modal' + (size === 'compact' ? ' rtw-modal--compact' : '')}
        role="dialog"
        aria-modal="true"
        data-testid="rtw-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="rtw-modal__header">{header}</header>
        <div className="rtw-modal__body">{body}</div>
        <footer className="rtw-modal__footer">
          {footer ?? (
            <>
              <div className="rtw-modal__footer-left">{footerLeft}</div>
              <div className="rtw-modal__footer-right">
                <button
                  type="button"
                  className="rtw-modal__btn"
                  data-testid="rtw-modal-cancel"
                  onClick={() => _attemptCancel(dirty, onCancel)}
                  disabled={saving}
                >
                  {cancelLabel}
                </button>
                <button
                  type="button"
                  className="rtw-modal__btn rtw-modal__btn--primary"
                  data-testid="rtw-modal-save"
                  onClick={onSave}
                  disabled={saveDisabled || saving || !onSave}
                >
                  {saving ? 'Saving…' : saveLabel}
                </button>
              </div>
            </>
          )}
        </footer>
      </div>
    </div>
  );
}

function _attemptCancel(dirty: boolean, onCancel: () => void) {
  if (dirty) {
    // Native confirm is fine for v1; F02-S02 can replace with a styled dialog.
    const proceed = window.confirm(
      'You have unsaved changes. Discard them?',
    );
    if (!proceed) return;
  }
  onCancel();
}
