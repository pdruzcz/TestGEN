import { Routes } from "@angular/router";

/** Lazy-loaded routing przeglądarki wyników (Story 6.4). */
export const RESULTS_ROUTES: Routes = [
  {
    path: "",
    title: "Wyniki analizy — TestGEN",
    loadComponent: () =>
      import("./results.component").then((m) => m.ResultsComponent),
  },
];
