import React from 'react';
import { createRoot, Root as ReactRoot } from 'react-dom/client';

import { Root } from './Root';
import './styles.css';

export interface MountOptions {
  topologyUrl: string;
  legacyAdminUrl: string;
  // Optional: injectable fetch (test seam). Production calls use window.fetch.
  fetchImpl?: typeof fetch;
}

export interface MountedRoot {
  unmount(): void;
}

export function mount(
  targetEl: HTMLElement | null,
  opts: MountOptions,
): MountedRoot | undefined {
  if (!targetEl || !(targetEl instanceof HTMLElement)) {
    // eslint-disable-next-line no-console
    console.warn(
      'runner-topology-widget: mount() called with an invalid target; widget not rendered.',
    );
    return undefined;
  }
  const reactRoot: ReactRoot = createRoot(targetEl);
  reactRoot.render(<Root {...opts} />);
  return {
    unmount() {
      reactRoot.unmount();
    },
  };
}

// Expose on `window` so the host page's one-line inline script can call
// `window.RunnerTopologyWidget.mount(...)` after the bundle loads.
if (typeof window !== 'undefined') {
  window.RunnerTopologyWidget = { mount };
}
