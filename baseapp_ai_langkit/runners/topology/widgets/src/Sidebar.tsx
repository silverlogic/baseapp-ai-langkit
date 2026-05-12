import React, { useEffect } from 'react';

import type { GraphNodeData } from './layout';
import { PromptSection } from './PromptSection';
import type { PromptSectionMode } from './PromptSection';
import type { SidebarPrompt } from './types';

export interface SidebarProps {
  node: GraphNodeData;
  onClose: () => void;
  // F02-S01 hooks: render Edit affordances on prompt panes and route clicks
  // to a parent-owned modal. Read-only callers (F01) omit both.
  promptMode?: PromptSectionMode;
  onEditPrompt?: (prompt: SidebarPrompt) => void;
  // Triggered when the user wants to view the default (pre-override) text
  // — read-only with copy-to-clipboard. Only meaningful in edit mode and
  // only fires when an override actually exists on the prompt.
  onViewDefault?: (prompt: SidebarPrompt) => void;
}

export function Sidebar({
  node,
  onClose,
  promptMode = 'view',
  onEditPrompt,
  onViewDefault,
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
          {node.model?.identifier && (
            <div className="rtw-sidebar__meta">model: {node.model.identifier}</div>
          )}
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
