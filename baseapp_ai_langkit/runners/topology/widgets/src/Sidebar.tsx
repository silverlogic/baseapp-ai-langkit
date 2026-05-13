import React, { useEffect } from 'react';

import type { GraphNodeData } from './layout';
import { PromptSection } from './PromptSection';
import type { PromptSectionMode } from './PromptSection';
import type { SidebarPrompt, TopologyModel } from './types';

export interface SidebarProps {
  node: GraphNodeData;
  onClose: () => void;
  // F02-S01 hooks: render Edit affordances on prompt panes and route clicks
  // to a parent-owned modal. Read-only callers (F01) omit both.
  promptMode?: PromptSectionMode;
  onEditPrompt?: (prompt: SidebarPrompt) => void;
  onViewDefault?: (prompt: SidebarPrompt) => void;
  // F02-S02 hook: route the model pane's Edit click to a parent-owned modal.
  onEditModel?: () => void;
}

export function Sidebar({
  node,
  onClose,
  promptMode = 'view',
  onEditPrompt,
  onViewDefault,
  onEditModel,
}: SidebarProps) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <aside className="rtw-sidebar" data-testid="rtw-sidebar">
      <header className="rtw-sidebar__header">
        <div>
          <h2 className="rtw-sidebar__title">{node.key}</h2>
          <div className="rtw-sidebar__meta">{node.class_name}</div>
          <div className="rtw-sidebar__meta">kind: {node.kind}</div>
        </div>
        <button
          type="button"
          className="rtw-sidebar__close"
          aria-label="Close sidebar"
          onClick={onClose}
        >
          ×
        </button>
      </header>

      <div className="rtw-sidebar__body">
        <ModelSection
          model={node.model}
          editable={promptMode === 'edit' && !!onEditModel}
          onEdit={onEditModel}
        />
        {node.prompts.map((prompt, idx) => (
          <PromptSection
            key={`${prompt.role}-${prompt.state_modifier_key ?? idx}`}
            mode={promptMode}
            prompt={prompt}
            onEditClick={onEditPrompt}
            onViewDefault={onViewDefault}
          />
        ))}
      </div>
    </aside>
  );
}

interface ModelSectionProps {
  model: TopologyModel;
  editable: boolean;
  onEdit?: () => void;
}

function ModelSection({ model, editable, onEdit }: ModelSectionProps) {
  const override = model.override;
  const orphan = !!override && !override.in_catalog;
  const defaultSummary =
    model.initializer_key && model.model_id
      ? `${model.initializer_key}:${model.model_id}`
      : 'not declared';

  return (
    <section className="rtw-prompt-section" data-testid="rtw-model-section">
      <header>
        <div className="rtw-prompt-section__role">Model</div>
        <div className="rtw-prompt-section__label">Chat model</div>
        <p className="rtw-prompt-section__description">
          Runner default: <code>{defaultSummary}</code>
          {Object.keys(model.params).length > 0 && (
            <> ({renderParams(model.params)})</>
          )}
        </p>
      </header>

      {orphan && override && (
        <div
          className="rtw-modal__warning"
          data-testid="rtw-model-section-orphan-warning"
          role="alert"
        >
          Override <code>{override.initializer_key}:{override.model_id}</code>{' '}
          is no longer in the catalog. Pick another model to save.
        </div>
      )}

      {override ? (
        <div
          className={
            'rtw-prompt-pane rtw-prompt-pane--override' +
            (editable ? ' rtw-prompt-pane--interactive' : '')
          }
          data-testid="rtw-override-model"
          onClick={editable ? onEdit : undefined}
          role={editable ? 'button' : undefined}
          tabIndex={editable ? 0 : undefined}
          onKeyDown={
            editable
              ? (e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onEdit?.();
                  }
                }
              : undefined
          }
        >
          <div className="rtw-prompt-pane__head">Override</div>
          <div className="rtw-prompt-pane__text">
            <code>{override.initializer_key}:{override.model_id}</code>
            {Object.keys(override.params).length > 0 && (
              <> ({renderParams(override.params)})</>
            )}
          </div>
          {editable && (
            <button
              type="button"
              className="rtw-prompt-pane__view-edit"
              data-testid="rtw-view-edit-model-override"
              aria-label="Edit model"
              onClick={(e) => {
                e.stopPropagation();
                onEdit?.();
              }}
            >
              View / Edit
            </button>
          )}
        </div>
      ) : (
        <div
          className={
            'rtw-prompt-pane rtw-prompt-pane--default' +
            (editable ? ' rtw-prompt-pane--interactive' : '')
          }
          data-testid="rtw-default-model"
          onClick={editable ? onEdit : undefined}
          role={editable ? 'button' : undefined}
          tabIndex={editable ? 0 : undefined}
          onKeyDown={
            editable
              ? (e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onEdit?.();
                  }
                }
              : undefined
          }
        >
          <div className="rtw-prompt-pane__head">Default</div>
          <div className="rtw-prompt-pane__text">
            <code>{defaultSummary}</code>
          </div>
          {editable && (
            <button
              type="button"
              className="rtw-prompt-pane__view-edit"
              data-testid="rtw-view-edit-model-default"
              aria-label="Edit model"
              onClick={(e) => {
                e.stopPropagation();
                onEdit?.();
              }}
            >
              View / Edit
            </button>
          )}
        </div>
      )}
    </section>
  );
}

function renderParams(params: Record<string, unknown>): string {
  return Object.entries(params)
    .map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`)
    .join(', ');
}
