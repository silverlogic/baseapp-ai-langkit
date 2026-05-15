// F03-S01 banner above the React Flow canvas.
//
// Renders the runner's identity (label + description) plus a one-line
// effective-default-model summary and an "Edit default model" button that
// opens `<ModelEditModal target='runner'>`. On topology-error payloads,
// falls back to a documented mount-root `data-runner-name` attribute (set
// by the change-view Django template) so the page header is never blank.

import React from 'react';

import type { AvailableLLMModelRow, TopologyRunner } from './types';

export interface BannerProps {
  // Non-null on a successful topology fetch (payload.runner is set);
  // `null` when the topology endpoint returned an error payload.
  runner: TopologyRunner | null;
  // Catalog list — used to look up the human-readable label for the
  // effective default. Empty array disables the Edit default model button.
  availableModels: AvailableLLMModelRow[];
  // Click handler for the Edit default model button. The parent (Root.tsx)
  // toggles a `editingRunnerDefault` state which mounts `<ModelEditModal>`.
  // When the button is disabled the handler is not wired up.
  onEditRunnerDefault: () => void;
  // Concrete admin URL for the catalog admin page (e.g.
  // `/admin/baseapp_ai_langkit_runners/availablellmmodel/`) shown in the
  // empty-catalog tooltip. Computed Django-side via `reverse()`.
  catalogAdminUrl?: string;
  // Mount root the widget was attached to. Read for the topology-error
  // fallback `data-runner-name` attribute. Defaults to looking up
  // `#runner-topology-root` via `documentRef`.
  mountElement?: HTMLElement | null;
  documentRef?: Document;
}

// Browser-side fallback for the topology-error path: derive the runner's
// class-name from the documented mount-root `data-runner-name` attribute
// (populated by the change-view Django template from `original.name`).
// Returns null when the attribute is missing — caller renders the literal
// `Runner` plus a `console.warn`.
function readMountClassNameFallback(
  mountElement: HTMLElement | null | undefined,
  documentRef: Document,
): string | null {
  const root =
    mountElement ?? documentRef.getElementById('runner-topology-root');
  const attr = root?.getAttribute('data-runner-name');
  if (!attr) return null;
  // Match rule 3's class-name-only convention by taking the trailing
  // dotted-path segment.
  const segments = attr.split('.');
  return segments[segments.length - 1] || attr;
}

export function Banner({
  runner,
  availableModels,
  onEditRunnerDefault,
  catalogAdminUrl,
  mountElement,
  documentRef,
}: BannerProps) {
  const docRef = documentRef ?? document;

  // Topology-error path: render the page header with a fallback identity
  // and hide the Edit button + tertiary summary entirely.
  if (runner === null) {
    return <BannerError mountElement={mountElement} documentRef={docRef} />;
  }

  const override = runner.default_model.override;
  const hasOverride = override !== null;
  const overrideInCatalog = hasOverride && override.in_catalog;
  // Mirrors the per-node prompt-pane override highlight (`.rtw-prompt-pane--override`)
  // so admins recognize the runner-level override at a glance with the same
  // visual cue used elsewhere in the widget. Only applies when the override
  // is non-null AND in-catalog — the orphan-warning glyph already covers the
  // "override exists but is broken" case.
  const showOverrideHighlight = overrideInCatalog;
  const hasCodeDefault =
    runner.default_model.initializer_key !== null &&
    runner.default_model.model_id !== null;

  const labelForKeyId = (initializerKey: string, modelId: string): string => {
    const row = availableModels.find(
      (r) => r.initializer_key === initializerKey && r.model_id === modelId,
    );
    return row?.label ?? modelId;
  };

  let summary: React.ReactNode;
  let showOrphanGlyph = false;
  if (overrideInCatalog) {
    summary = (
      <>
        Default model:{' '}
        <strong>
          {labelForKeyId(override.initializer_key, override.model_id)} (
          {override.initializer_key})
        </strong>{' '}
        — override
      </>
    );
  } else if (hasOverride && !overrideInCatalog) {
    // Orphan override: surface as a warning glyph next to the code default.
    showOrphanGlyph = true;
    if (hasCodeDefault) {
      summary = (
        <>
          Default model:{' '}
          <strong>
            {labelForKeyId(
              runner.default_model.initializer_key!,
              runner.default_model.model_id!,
            )}{' '}
            ({runner.default_model.initializer_key})
          </strong>{' '}
          — runner default
        </>
      );
    } else {
      summary = <>Default model: <strong>not declared</strong></>;
    }
  } else if (hasCodeDefault) {
    summary = (
      <>
        Default model:{' '}
        <strong>
          {labelForKeyId(
            runner.default_model.initializer_key!,
            runner.default_model.model_id!,
          )}{' '}
          ({runner.default_model.initializer_key})
        </strong>{' '}
        — runner default
      </>
    );
  } else {
    summary = <>Default model: <strong>not declared</strong></>;
  }

  const catalogEmpty = availableModels.length === 0;
  const tooltip = catalogEmpty
    ? catalogAdminUrl
      ? `No models in the AvailableLLMModel catalog. Add one in ${catalogAdminUrl}.`
      : 'No models in the AvailableLLMModel catalog. Add one in Django admin → Available LLM models.'
    : undefined;

  return (
    <div className="rtw-runner-banner" data-testid="rtw-runner-banner">
      <div className="rtw-runner-banner__identity">
        <h1
          className="rtw-runner-banner__label"
          data-testid="rtw-runner-banner-label"
        >
          {runner.label}
        </h1>
        {runner.description && (
          <p
            className="rtw-runner-banner__description"
            data-testid="rtw-runner-banner-description"
          >
            {runner.description}
          </p>
        )}
      </div>
      <div className="rtw-runner-banner__summary-row">
        <span
          className={
            'rtw-runner-banner__summary' +
            (showOverrideHighlight ? ' rtw-runner-banner__summary--override' : '')
          }
          data-testid="rtw-runner-banner-summary"
        >
          {summary}
          {showOrphanGlyph && (
            <span
              className="rtw-runner-banner__orphan-glyph"
              data-testid="rtw-runner-banner-orphan-glyph"
              title="Override points at a catalog entry that no longer exists; runtime is using the code default."
              aria-label="Override out of catalog"
            >
              ⚠
            </span>
          )}
        </span>
        <button
          type="button"
          className="rtw-runner-banner__edit-btn"
          data-testid="rtw-runner-banner-edit"
          onClick={catalogEmpty ? undefined : onEditRunnerDefault}
          disabled={catalogEmpty}
          title={tooltip}
        >
          Edit default model
        </button>
      </div>
    </div>
  );
}

interface BannerErrorProps {
  mountElement?: HTMLElement | null;
  documentRef: Document;
}

function BannerError({ mountElement, documentRef }: BannerErrorProps) {
  const fallback = readMountClassNameFallback(mountElement, documentRef);
  // Single-warn semantics: emit once per render only when the attribute is
  // genuinely missing. The widget MUST NOT read `document.title` or trigger
  // a second topology fetch (per the spec).
  if (fallback === null && typeof console !== 'undefined') {
    console.warn(
      'baseapp-ai-langkit: Mount root is missing the data-runner-name attribute; ' +
        'banner falling back to literal label. Verify the change-view template emits ' +
        'data-runner-name="{{ original.name }}".',
    );
  }
  return (
    <div
      className="rtw-runner-banner rtw-runner-banner--error"
      data-testid="rtw-runner-banner"
    >
      <div className="rtw-runner-banner__identity">
        <h1
          className="rtw-runner-banner__label"
          data-testid="rtw-runner-banner-label"
        >
          {fallback ?? 'Runner'}
        </h1>
      </div>
    </div>
  );
}
