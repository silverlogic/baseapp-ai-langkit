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

export interface TopologyModel {
  identifier?: string;
}

export interface TopologyNode {
  key: string;
  class_name: string;
  kind: TopologyNodeKind;
  model?: TopologyModel | null;
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
