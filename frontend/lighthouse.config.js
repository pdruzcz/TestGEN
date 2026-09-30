/**
 * Story 6.9, AC8 — konfiguracja Lighthouse CI (@lhci/cli).
 * Budżet: accessibility > 95 punktów (asercja >= 0.95 blokuje pipeline).
 *
 * Uruchomienie: `npm run lighthouse:ci` (lhci autorun --config=lighthouse.config.js)
 */
module.exports = {
  ci: {
    collect: {
      url: [
        (process.env.APP_BASE_URL || "http://localhost:4200") + "/login",
        (process.env.APP_BASE_URL || "http://localhost:4200") + "/register",
      ],
      numberOfRuns: 1,
      settings: {
        onlyCategories: ["accessibility"],
        // Aplikacja SPA — czekaj na pełne wyrenderowanie.
        maxWaitForLoad: 45000,
      },
    },
    assert: {
      assertions: {
        // AC8: wynik accessibility > 95 punktów.
        "categories:accessibility": ["error", { minScore: 0.95 }],
      },
    },
    upload: {
      target: "filesystem",
      outputDir: "./lighthouse-reports",
    },
  },
};
