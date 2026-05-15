// Topology JSON contract — must match `runner-topology-extraction`'s payload.
//
// The server emits a structured success/error envelope; `error` is optional
// and present only on failure. State-modifier prompts arrive as an array with
// a stable string `key` (the integer index serialized as a string).

export type TopologyNodeKind = 'agent' | 'worker';

export type TopologyEdgeKind = 'normal' | 'conditional';

export type TopologyErrorCode =
  | 'runner_unregistered'
  | 'topology_builder_not_declared'
  | 'workflow_init_failed'
  | 'unknown';

export interface TopologyError {
  code: TopologyErrorCode;
  message: string;
}

export interface PromptOverride {
  text: string;
  saved_at: string | null;
}

export interface PromptBlock {
  description: string;
  required_placeholders: string[];
  default_text: string;
  override?: PromptOverride | null;
}

export interface StateModifierPromptBlock extends PromptBlock {
  key: string;
}

export interface ModelOverride {
  initializer_key: string;
  model_id: string;
  params: Record<string, unknown>;
  saved_at: string | null;
  // `false` when the override's (initializer_key, model_id) no longer matches
  // any AvailableLLMModel row — the modal shows a warning and disables save
  // until a valid catalog entry is picked.
  in_catalog: boolean;
}

// Per-node `model` field. Defaults come from the runner's
// `default_model_metadata` classattr; `null` initializer_key / model_id when
// the runner hasn't declared it.
export interface TopologyModel {
  initializer_key: string | null;
  model_id: string | null;
  params: Record<string, unknown>;
  override: ModelOverride | null;
}

// Topology payload's root `runner` block (F03-S01). Carries the runner's
// display identity (label + description) and the runner-level default-model
// shape — same as `TopologyModel` but one rung above the per-node `model`.
// `null` when the topology endpoint returned an error payload.
export interface TopologyRunner {
  label: string;
  description: string | null;
  default_model: TopologyModel;
}

// Catalog row, shipped at the topology payload root for the model edit modal.
// `allowed_params` is derived server-side from the matching registered
// initializer (empty array when the initializer is unregistered).
export interface AvailableLLMModelRow {
  label: string;
  initializer_key: string;
  model_id: string;
  default_params: Record<string, unknown>;
  allowed_params: string[];
}

export interface TopologyNode {
  key: string;
  class_name: string;
  kind: TopologyNodeKind;
  // Server-side contract emits this for every node (rule 4 of S02). Marked
  // optional in TS so older test fixtures (pre-S02) don't need rewriting;
  // `topologyToGraph` defaults to a null/null/{}/null model when missing.
  model?: TopologyModel;
  usage_prompt?: PromptBlock | null;
  state_modifier_prompts?: StateModifierPromptBlock[];
  // Persisted admin-curated position. When every node has one the widget
  // skips dagre and uses these verbatim; partial coverage falls back to
  // full auto-layout. Set by the "Save layout" flow.
  position?: { x: number; y: number } | null;
}

export interface TopologyEdge {
  source: string;
  target: string;
  kind: TopologyEdgeKind;
}

export interface TopologyResponse {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
  // Optional in TS for fixture compatibility — runtime contract emits an array
  // (possibly empty) per the topology-extraction delta spec.
  available_models?: AvailableLLMModelRow[];
  // F03-S01 root block — present on every successful extraction, `null` on
  // error payloads. Optional in TS so older test fixtures (pre-F03) keep
  // working; consumers tolerate `undefined` the same way they handle `null`.
  runner?: TopologyRunner | null;
  error?: TopologyError | null;
}

// Sidebar view-model. The layout module flattens usage + state-modifier
// prompts into a single ordered list so `<PromptSection>` can render either
// shape identically — they differ only in their role label.

export type SidebarPromptRole = 'usage' | 'state_modifier';

export interface SidebarPrompt {
  role: SidebarPromptRole;
  label: string;
  prompt: PromptBlock;
  // F02-S01 endpoint addressing: the save URL is per-target. The save flow
  // resolves the URL from these fields plus the runner pk in component context.
  // `state_modifier_key` is the stable string the topology emits for that entry.
  state_modifier_key?: string;
}

// Public global the bundle exposes once mounted. `mount.tsx` populates this.
declare global {
  interface Window {
    RunnerTopologyWidget?: {
      mount: typeof import('./mount').mount;
    };
  }
}
