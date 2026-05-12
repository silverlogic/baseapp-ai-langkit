import React, { useMemo, useState } from 'react';

import { EditModalShell } from './EditModalShell';
import {
  PromptSaveError,
  savePrompt,
} from './savePrompt';
import type { SidebarPrompt } from './types';

export interface PromptEditModalProps {
  prompt: SidebarPrompt;
  saveUrl: string;
  onCancel: () => void;
  // Called once the server returns HTTP 200. The parent is responsible for
  // re-fetching the topology endpoint and closing the modal.
  onSaved: () => void | Promise<void>;
  fetchImpl?: typeof fetch;
  // Optional test seam: a `document` object to read the CSRF cookie from.
  documentRef?: Document;
}

export function PromptEditModal({
  prompt,
  saveUrl,
  onCancel,
  onSaved,
  fetchImpl,
  documentRef,
}: PromptEditModalProps) {
  const initial = prompt.prompt.override?.text ?? prompt.prompt.default_text;
  const [text, setText] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<PromptSaveError | null>(null);

  // Mirror `BasePromptSchema.validate`: a placeholder is satisfied only when
  // the format-string token `{name}` appears in the text — not when the
  // bare name happens to be a substring (e.g., `{nameXYZ` slipped through
  // the old naive check). The server runs the authoritative version of
  // this; the client hint is informational only.
  const missing = useMemo(
    () =>
      prompt.prompt.required_placeholders.filter(
        (p) => !text.includes('{' + p + '}'),
      ),
    [text, prompt.prompt.required_placeholders],
  );

  const dirty = text !== initial;
  // Save is NEVER blocked by missing placeholders — the user must be able
  // to fire the save and see the structured server error. The hint below
  // the textarea is the only client signal; the server's
  // `missing_placeholders` envelope is the authority.
  const saveDisabled = saving;

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    const result = await savePrompt(
      saveUrl,
      text,
      fetchImpl ?? window.fetch,
      documentRef ?? document,
    );
    setSaving(false);
    if (result.ok) {
      await onSaved();
      return;
    }
    setError(result.error);
  };

  return (
    <EditModalShell
      isOpen
      onCancel={onCancel}
      onSave={handleSave}
      saveDisabled={saveDisabled}
      saving={saving}
      dirty={dirty}
      disableOutsideDismiss

      header={
        <>
          <h3 className="rtw-modal__title" data-testid="rtw-modal-title">
            {prompt.label}
          </h3>
          <p
            className="rtw-modal__description"
            data-testid="rtw-modal-description"
          >
            {prompt.prompt.description}
          </p>
          {prompt.prompt.required_placeholders.length > 0 && (
            <div className="rtw-placeholders" aria-label="Required placeholders">
              {prompt.prompt.required_placeholders.map((p) => (
                <span key={p} className="rtw-placeholder">
                  {p}
                </span>
              ))}
            </div>
          )}
        </>
      }
      body={
        <>
          <textarea
            className="rtw-modal__textarea"
            data-testid="rtw-modal-textarea"
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={saving}
            aria-label={`Edit ${prompt.label}`}
          />
          {missing.length > 0 && (
            <div className="rtw-modal__hint" data-testid="rtw-modal-hint">
              Missing required placeholder(s): {missing.join(', ')}
            </div>
          )}
          {error && (
            <div className="rtw-modal__error" data-testid="rtw-modal-error">
              {error.message}
              {error.details?.missing && error.details.missing.length > 0 && (
                <> ({error.details.missing.join(', ')})</>
              )}
            </div>
          )}
        </>
      }
    />
  );
}
