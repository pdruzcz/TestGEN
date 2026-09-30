import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['src/test-setup.ts'],
    include: ['src/**/*.spec.ts'],
    reporters: ['default', 'junit'],
    outputFile: {
      junit: 'test-results/frontend-results.xml',
    },
    testTimeout: 15_000,
    // Hooki (beforeEach z TestBed/compileComponents) pod pełnym suite'em na
    // zajętej maszynie potrafią przekraczać domyślne 10 s — to koszt setupu,
    // nie błąd logiki testu (znana klasa flake ng-test). 30 s głównie dla CI
    // i lokalnych runów równoległych z backendem.
    hookTimeout: 30_000,
    coverage: {
      provider: 'v8',
      // Story 6.13 (AC8) — lcov dla narzędzi coverage (Sonar/IDE).
      reporter: ['text', 'html', 'cobertura', 'lcov'],
      reportsDirectory: 'coverage/',
      thresholds: {
        statements: 80,
      },
    },
  },
});
