// F03-S01 banner — topology-error fallback path.
//
// When the topology endpoint returns an error payload (`runner: null`), the
// widget reads `data-runner-name` from the mount root and derives the
// class-name-only label by splitting on `.`. Absent attribute → literal
// `Runner` + single `console.warn`. Widget MUST NOT read `document.title`
// or trigger a second topology fetch.

import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { Banner } from '../src/Banner';

function makeMount(attrValue?: string): HTMLDivElement {
  const div = document.createElement('div');
  div.id = 'runner-topology-root';
  if (attrValue !== undefined) {
    div.setAttribute('data-runner-name', attrValue);
  }
  return div;
}

describe('Banner — topology-error fallback', () => {
  let warnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
  });
  afterEach(() => {
    warnSpy.mockRestore();
  });

  it('derives class-name from data-runner-name when present', () => {
    const mount = makeMount(
      'testproject.apps.example.runners.BookMovieExpertChatRunner',
    );
    render(
      <Banner
        runner={null}
        availableModels={[]}
        onEditRunnerDefault={() => {}}
        mountElement={mount}
      />,
    );
    expect(screen.getByTestId('rtw-runner-banner-label').textContent).toBe(
      'BookMovieExpertChatRunner',
    );
    expect(warnSpy).not.toHaveBeenCalled();
  });

  it('renders literal "Runner" + emits console.warn when attribute is missing', () => {
    const mount = makeMount(); // no data-runner-name
    render(
      <Banner
        runner={null}
        availableModels={[]}
        onEditRunnerDefault={() => {}}
        mountElement={mount}
      />,
    );
    expect(screen.getByTestId('rtw-runner-banner-label').textContent).toBe(
      'Runner',
    );
    expect(warnSpy).toHaveBeenCalledTimes(1);
    expect(warnSpy.mock.calls[0][0]).toMatch(/data-runner-name/);
  });

  it('hides Edit default model button + description line + tertiary summary', () => {
    const mount = makeMount('pkg.path.MyRunner');
    render(
      <Banner
        runner={null}
        availableModels={[
          {
            label: 'GPT-4o mini',
            initializer_key: 'openai',
            model_id: 'gpt-4o-mini',
            default_params: {},
            allowed_params: ['temperature'],
          },
        ]}
        onEditRunnerDefault={() => {}}
        mountElement={mount}
      />,
    );
    expect(screen.queryByTestId('rtw-runner-banner-edit')).toBeNull();
    expect(screen.queryByTestId('rtw-runner-banner-description')).toBeNull();
    expect(screen.queryByTestId('rtw-runner-banner-summary')).toBeNull();
  });

  it('does NOT read document.title in the error fallback', () => {
    const mount = makeMount('pkg.path.SomeRunner');
    // Spy on the document.title getter.
    const titleSpy = vi.fn();
    Object.defineProperty(document, 'title', {
      configurable: true,
      get: () => {
        titleSpy();
        return '';
      },
    });
    try {
      render(
        <Banner
          runner={null}
          availableModels={[]}
          onEditRunnerDefault={() => {}}
          mountElement={mount}
        />,
      );
      expect(titleSpy).not.toHaveBeenCalled();
    } finally {
      // Restore the default title property.
      Object.defineProperty(document, 'title', {
        configurable: true,
        writable: true,
        value: '',
      });
    }
  });
});
