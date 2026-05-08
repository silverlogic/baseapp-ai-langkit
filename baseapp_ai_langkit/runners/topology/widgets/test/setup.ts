import '@testing-library/jest-dom/vitest';

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

class IntersectionObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return [];
  }
  root: Element | null = null;
  rootMargin = '';
  thresholds: ReadonlyArray<number> = [];
}

if (!globalThis.ResizeObserver) {
  // @ts-expect-error stub
  globalThis.ResizeObserver = ResizeObserverStub;
}

if (!globalThis.IntersectionObserver) {
  // @ts-expect-error stub
  globalThis.IntersectionObserver = IntersectionObserverStub;
}

// happy-dom does not provide DOMRect in older versions; provide a minimal stub.
if (typeof Element !== 'undefined' && !Element.prototype.getBoundingClientRect) {
  Element.prototype.getBoundingClientRect = function () {
    return {
      x: 0,
      y: 0,
      width: 800,
      height: 600,
      top: 0,
      left: 0,
      right: 800,
      bottom: 600,
      toJSON() {
        return this;
      },
    } as DOMRect;
  };
}
