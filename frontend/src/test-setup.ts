// Builder `@angular/build:unit-test` inicjalizuje TestBed przed tym plikiem,
// więc tutaj zostają wyłącznie polyfille środowiska.

// jsdom nie implementuje matchMedia, a ThemeService (WCAG: prefers-contrast,
// prefers-reduced-motion) go wymaga. Domyślnie nic nie pasuje — testy, które
// potrzebują innego zachowania, podmieniają to przez vi.spyOn.
if (typeof window !== "undefined" && !window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    configurable: true,
    value: (query: string) =>
      ({
        matches: false,
        media: query,
        onchange: null,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
        addListener: () => undefined,
        removeListener: () => undefined,
        dispatchEvent: () => false,
      }) as unknown as MediaQueryList,
  });
}
