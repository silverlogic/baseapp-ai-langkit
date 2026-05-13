import React, { useEffect, useMemo, useState } from 'react';

import { EditModalShell } from './EditModalShell';
import {
  ModelSaveError,
  resetModelOverride,
  saveModelOverride,
} from './saveModel';
import type { AvailableLLMModelRow, TopologyModel } from './types';

export interface ModelEditModalProps {
  nodeKey: string;
  model: TopologyModel;
  availableModels: AvailableLLMModelRow[];
  saveUrl: string;
  onCancel: () => void;
  // Called once the server returns HTTP 200. The parent is responsible for
  // re-fetching the topology endpoint and closing the modal.
  onSaved: () => void | Promise<void>;
  fetchImpl?: typeof fetch;
  documentRef?: Document;
  // Injectable confirm hook — defaults to window.confirm. The modal asks for
  // confirmation before resetting an override since the action is destructive
  // (the persisted row is deleted server-side).
  confirmImpl?: (message: string) => boolean;
}

type RowKey = string; // `${initializer_key}:${model_id}`

function rowKey(initializerKey: string, modelId: string): RowKey {
  return `${initializerKey}:${modelId}`;
}

// Pick the default selection for the picker:
//   1. The current override entry, when it exists AND is in_catalog.
//   2. The runner default entry, when it matches a catalog row.
//   3. None (admin must pick).
function pickInitialSelection(
  model: TopologyModel,
  catalog: AvailableLLMModelRow[],
): RowKey {
  const byKey = new Set(
    catalog.map((r) => rowKey(r.initializer_key, r.model_id)),
  );
  if (model.override && model.override.in_catalog) {
    const key = rowKey(model.override.initializer_key, model.override.model_id);
    if (byKey.has(key)) return key;
  }
  if (model.initializer_key && model.model_id) {
    const key = rowKey(model.initializer_key, model.model_id);
    if (byKey.has(key)) return key;
  }
  return '';
}

// Validate a numeric param against the global ranges (mirror of the server's
// `_validate_param_values`). Returns null when valid, an error string otherwise.
function paramError(name: string, value: unknown): string | null {
  if (name === 'temperature' || name === 'top_p') {
    if (typeof value !== 'number' || Number.isNaN(value)) return 'must be a number';
    if (name === 'temperature' && (value < 0 || value > 2)) return 'must be 0.0–2.0';
    if (name === 'top_p' && (value < 0 || value > 1)) return 'must be 0.0–1.0';
  } else if (name === 'max_tokens') {
    if (typeof value !== 'number' || !Number.isInteger(value) || value <= 0) {
      return 'must be a positive integer';
    }
  }
  return null;
}

export function ModelEditModal({
  nodeKey,
  model,
  availableModels,
  saveUrl,
  onCancel,
  onSaved,
  fetchImpl,
  documentRef,
  confirmImpl,
}: ModelEditModalProps) {
  const initialSelection = useMemo(
    () => pickInitialSelection(model, availableModels),
    [model, availableModels],
  );
  const [selectedKey, setSelectedKey] = useState<RowKey>(initialSelection);
  const [params, setParams] = useState<Record<string, unknown>>(
    model.override?.in_catalog ? { ...model.override.params } : {},
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<ModelSaveError | null>(null);

  const selectedRow = useMemo(
    () =>
      availableModels.find(
        (r) => rowKey(r.initializer_key, r.model_id) === selectedKey,
      ) ?? null,
    [availableModels, selectedKey],
  );

  const overrideOutOfCatalog =
    !!model.override && !model.override.in_catalog;

  // Discard params keys the newly-picked initializer doesn't allow.
  useEffect(() => {
    if (!selectedRow) return;
    setParams((prev) => {
      const next: Record<string, unknown> = {};
      for (const k of selectedRow.allowed_params) {
        if (k in prev) next[k] = prev[k];
      }
      return next;
    });
  }, [selectedRow]);

  const inlineErrors = useMemo(() => {
    if (!selectedRow) return {} as Record<string, string>;
    const errs: Record<string, string> = {};
    for (const k of selectedRow.allowed_params) {
      if (k in params) {
        const err = paramError(k, params[k]);
        if (err) errs[k] = err;
      }
    }
    return errs;
  }, [params, selectedRow]);

  const dirty =
    selectedKey !== initialSelection ||
    JSON.stringify(params) !==
      JSON.stringify(
        model.override?.in_catalog ? model.override.params : {},
      );

  const handleSave = async () => {
    if (!selectedRow) return;
    setSaving(true);
    setError(null);
    const result = await saveModelOverride(
      saveUrl,
      {
        initializer_key: selectedRow.initializer_key,
        model_id: selectedRow.model_id,
        params,
      },
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

  const handleReset = async () => {
    const confirm = confirmImpl ?? window.confirm.bind(window);
    const proceed = confirm(
      'Reset this node to the runner default model? The current override will be deleted.',
    );
    if (!proceed) return;
    setSaving(true);
    setError(null);
    const result = await resetModelOverride(
      saveUrl,
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

  const defaultSummary =
    model.initializer_key && model.model_id
      ? `${model.initializer_key}:${model.model_id}`
      : 'not declared';

  return (
    <EditModalShell
      isOpen
      onCancel={onCancel}
      onSave={handleSave}
      saveDisabled={!selectedRow || Object.keys(inlineErrors).length > 0 || saving}
      saving={saving}
      dirty={dirty}
      disableOutsideDismiss
      size="compact"
      footerLeft={
        model.override ? (
          <button
            type="button"
            className="rtw-modal__btn rtw-modal__btn--danger"
            data-testid="rtw-model-modal-reset"
            onClick={handleReset}
            disabled={saving}
          >
            Reset to default
          </button>
        ) : null
      }
      header={
        <>
          <h3 className="rtw-modal__title" data-testid="rtw-model-modal-title">
            Model for node {nodeKey}
          </h3>
          <p
            className="rtw-modal__description"
            data-testid="rtw-model-modal-default"
          >
            Runner default: <code>{defaultSummary}</code>
          </p>
        </>
      }
      body={
        <>
          {overrideOutOfCatalog && (
            <div
              className="rtw-modal__warning"
              data-testid="rtw-model-modal-orphan-warning"
              role="alert"
            >
              Existing override <code>{model.override?.initializer_key}:{model.override?.model_id}</code>{' '}
              is no longer in the catalog. Pick another model to save.
            </div>
          )}
          {availableModels.length === 0 ? (
            <div
              className="rtw-modal__empty"
              data-testid="rtw-model-modal-empty"
            >
              No models configured for this project. Add one in Django admin →
              Available LLM models.
            </div>
          ) : (
            <>
              <label className="rtw-model-modal__label">
                Model
                <select
                  className="rtw-model-modal__select"
                  data-testid="rtw-model-modal-picker"
                  value={selectedKey}
                  onChange={(e) => setSelectedKey(e.target.value)}
                  disabled={saving}
                >
                  <option value="">— pick a model —</option>
                  {availableModels.map((row) => (
                    <option
                      key={rowKey(row.initializer_key, row.model_id)}
                      value={rowKey(row.initializer_key, row.model_id)}
                    >
                      {row.label} ({row.initializer_key}:{row.model_id})
                    </option>
                  ))}
                </select>
              </label>

              {selectedRow && (
                <div
                  className="rtw-model-modal__params"
                  data-testid="rtw-model-modal-params"
                >
                  {selectedRow.allowed_params.length === 0 && (
                    <div className="rtw-modal__hint">
                      No tunable params declared for this initializer.
                    </div>
                  )}
                  {selectedRow.allowed_params.map((paramName) => (
                    <ParamControl
                      key={paramName}
                      name={paramName}
                      value={params[paramName]}
                      defaultValue={selectedRow.default_params[paramName]}
                      onChange={(value) =>
                        setParams((prev) => {
                          const next = { ...prev };
                          if (value === null || value === undefined || value === '') {
                            delete next[paramName];
                          } else {
                            next[paramName] = value;
                          }
                          return next;
                        })
                      }
                      error={inlineErrors[paramName]}
                      disabled={saving}
                    />
                  ))}
                </div>
              )}
            </>
          )}

          {error && (
            <div className="rtw-modal__error" data-testid="rtw-model-modal-error">
              {error.message}
              {error.details?.disallowed && error.details.disallowed.length > 0 && (
                <> (disallowed: {error.details.disallowed.join(', ')})</>
              )}
              {error.details?.invalid && error.details.invalid.length > 0 && (
                <> (invalid: {error.details.invalid.join(', ')})</>
              )}
            </div>
          )}
        </>
      }
    />
  );
}

interface ParamControlProps {
  name: string;
  value: unknown;
  defaultValue: unknown;
  onChange: (value: number | string | null) => void;
  error?: string;
  disabled?: boolean;
}

const PARAM_HELP_TEXT: Record<string, string> = {
  temperature:
    'Range 0.0–2.0. Lower values are deterministic; higher values produce more varied output.',
  max_tokens:
    'Maximum number of tokens the model may generate in its reply. Positive integer.',
  top_p:
    'Range 0.0–1.0. Nucleus sampling cutoff — restricts the model to tokens whose cumulative probability is below top_p.',
};

function ParamControl({
  name,
  value,
  defaultValue,
  onChange,
  error,
  disabled,
}: ParamControlProps) {
  const isNumeric =
    name === 'temperature' || name === 'top_p' || name === 'max_tokens';
  const placeholder =
    defaultValue === undefined || defaultValue === null
      ? undefined
      : String(defaultValue);
  const help = PARAM_HELP_TEXT[name];

  return (
    <label
      className="rtw-model-modal__param"
      data-testid={`rtw-model-modal-param-${name}`}
    >
      <span className="rtw-model-modal__param-label">{name}</span>
      <input
        className="rtw-model-modal__param-input"
        type={isNumeric ? 'number' : 'text'}
        step={name === 'temperature' || name === 'top_p' ? 0.1 : 1}
        min={name === 'max_tokens' ? 1 : undefined}
        value={
          value === undefined || value === null
            ? ''
            : (value as number | string)
        }
        placeholder={placeholder}
        onChange={(e) => {
          const raw = e.target.value;
          if (raw === '') {
            onChange(null);
            return;
          }
          if (isNumeric) {
            const num = Number(raw);
            onChange(Number.isNaN(num) ? raw : num);
          } else {
            onChange(raw);
          }
        }}
        disabled={disabled}
      />
      {help && (
        <span
          className="rtw-model-modal__param-help"
          data-testid={`rtw-model-modal-param-help-${name}`}
        >
          {help}
        </span>
      )}
      {error && (
        <span
          className="rtw-model-modal__param-error"
          data-testid={`rtw-model-modal-param-error-${name}`}
        >
          {error}
        </span>
      )}
    </label>
  );
}
