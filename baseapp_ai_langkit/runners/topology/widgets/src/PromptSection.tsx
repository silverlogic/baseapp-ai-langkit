import { useState } from 'react';

import type { SidebarPrompt } from './types';

// Locale-aware "Saved <when>" formatter for ISO timestamps coming off the
// server. Falls back to the raw ISO on malformed input so we never blank
// out a saved-at line entirely. The full ISO is still available on hover
// via the parent element's `title` attribute.
function formatSavedAt(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(d);
  } catch {
    return iso;
  }
}

export type PromptSectionMode = 'view' | 'edit';

export interface PromptSectionProps {
  mode: PromptSectionMode;
  prompt: SidebarPrompt;
  // Open the edit modal for this prompt's override. When there is no
  // override yet, this is the "create the first override" path.
  onEditClick?: (prompt: SidebarPrompt) => void;
  // Open the read-only default-prompt view modal (with copy-to-clipboard).
  // Only meaningful when an override exists; otherwise the default pane is
  // editable directly via `onEditClick`.
  onViewDefault?: (prompt: SidebarPrompt) => void;
}

export function PromptSection({
  mode,
  prompt,
  onEditClick,
  onViewDefault,
}: PromptSectionProps) {
  const { role, label, prompt: block } = prompt;
  const hasOverride = !!block.override && block.override.text.length > 0;
  const editable = mode === 'edit' && !!onEditClick;
  const onEdit = editable ? () => onEditClick!(prompt) : undefined;
  // When override exists, clicking the default pane opens the *view* modal
  // — default is reference, override is the operative copy. Without an
  // override, the default pane is the editable target.
  const onDefaultClick = !editable
    ? undefined
    : hasOverride
      ? onViewDefault
        ? () => onViewDefault(prompt)
        : undefined
      : onEdit;

  return (
    <section
      className="rtw-prompt-section"
      data-testid={`rtw-prompt-${role}`}
    >
      <PromptHeader
        role={role}
        label={label}
        description={block.description}
      />

      {block.required_placeholders.length > 0 && (
        <PromptPlaceholders placeholders={block.required_placeholders} />
      )}

      {hasOverride && block.override ? (
        <div className="rtw-prompt-stack">
          {/* Default dropdown first, override below — per smoke-test feedback. */}
          <CollapsibleDefault
            role={role}
            text={block.default_text}
            onClick={onDefaultClick}
            paneAction={onDefaultClick ? 'view' : undefined}
          />
          <PromptPane
            role={role}
            variant="override"
            text={block.override.text}
            savedAt={block.override.saved_at ?? undefined}
            onClick={onEdit}
            paneAction={onEdit ? 'edit' : undefined}
          />
        </div>
      ) : (
        <PromptPane
          role={role}
          variant="default"
          text={block.default_text}
          onClick={onEdit}
          paneAction={onEdit ? 'edit' : undefined}
        />
      )}
    </section>
  );
}

interface PromptHeaderProps {
  role: SidebarPrompt['role'];
  label: string;
  description: string;
}

function PromptHeader({ role, label, description }: PromptHeaderProps) {
  return (
    <header>
      <div className="rtw-prompt-section__role">
        {role === 'usage' ? 'Usage' : 'State modifier'}
      </div>
      <div className="rtw-prompt-section__label">{label}</div>
      <p className="rtw-prompt-section__description">{description}</p>
    </header>
  );
}

interface PromptPlaceholdersProps {
  placeholders: string[];
}

function PromptPlaceholders({ placeholders }: PromptPlaceholdersProps) {
  return (
    <div className="rtw-placeholders" aria-label="Required placeholders">
      {placeholders.map((p) => (
        <span key={p} className="rtw-placeholder">
          {p}
        </span>
      ))}
    </div>
  );
}

interface CollapsibleDefaultProps {
  role: SidebarPrompt['role'];
  text: string;
  onClick?: () => void;
  paneAction?: PaneAction;
}

function CollapsibleDefault({
  role,
  text,
  onClick,
  paneAction,
}: CollapsibleDefaultProps) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="rtw-collapsible">
      <button
        type="button"
        className="rtw-collapsible__toggle"
        data-testid={`rtw-toggle-default-${role}`}
        aria-expanded={expanded}
        onClick={() => setExpanded((e) => !e)}
      >
        <span className="rtw-collapsible__chevron" aria-hidden="true">
          {expanded ? '▾' : '▸'}
        </span>
        {expanded ? 'Hide default' : 'See default'}
      </button>
      <div
        className="rtw-collapsible__body"
        data-testid={`rtw-collapsible-default-${role}`}
        hidden={!expanded}
      >
        <PromptPane
          role={role}
          variant="default"
          text={text}
          onClick={onClick}
          paneAction={paneAction}
        />
      </div>
    </div>
  );
}

type PaneAction = 'edit' | 'view';

interface PromptPaneProps {
  role: SidebarPrompt['role'];
  variant: 'default' | 'override';
  text: string;
  savedAt?: string;
  onClick?: () => void;
  // 'edit' → label the inline CTA "View / Edit"; 'view' → "View" only.
  paneAction?: PaneAction;
}

function PromptPane({
  role,
  variant,
  text,
  savedAt,
  onClick,
  paneAction,
}: PromptPaneProps) {
  const interactive = !!onClick;
  const ariaLabel =
    paneAction === 'view'
      ? `View default ${role === 'usage' ? 'usage prompt' : 'state modifier prompt'}`
      : `Edit ${role === 'usage' ? 'usage prompt' : 'state modifier prompt'}`;
  const ctaLabel = paneAction === 'view' ? 'View' : 'View / Edit';
  return (
    <div
      className={
        'rtw-prompt-pane' +
        ` rtw-prompt-pane--${variant}` +
        (interactive ? ' rtw-prompt-pane--interactive' : '')
      }
      data-testid={`rtw-${variant}-${role}`}
      onClick={onClick}
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
      onKeyDown={
        interactive
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onClick?.();
              }
            }
          : undefined
      }
    >
      <div className="rtw-prompt-pane__head">
        {variant === 'default' ? 'Default' : 'Override'}
      </div>
      <div className="rtw-prompt-pane__text">{text}</div>
      {variant === 'override' && savedAt && (
        <div
          className="rtw-prompt-pane__saved-at"
          title={savedAt /* full ISO on hover for power users */}
        >
          Saved {formatSavedAt(savedAt)}
        </div>
      )}
      {interactive && (
        <button
          type="button"
          className="rtw-prompt-pane__view-edit"
          data-testid={`rtw-view-edit-${role}-${variant}`}
          aria-label={ariaLabel}
          onClick={(e) => {
            e.stopPropagation();
            onClick?.();
          }}
        >
          {ctaLabel}
        </button>
      )}
    </div>
  );
}
