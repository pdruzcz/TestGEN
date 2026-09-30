import { Routes } from '@angular/router';

/**
 * Integracje: hosting kodu (8.1 GitHub, 8.2 GitLab), historia status checków
 * (8.3), webhooki wychodzące (8.7) i synchronizacja z TMS (8.11).
 */
export const INTEGRATIONS_ROUTES: Routes = [
  {
    path: 'github',
    title: 'Integracja GitHub — TestGEN',
    loadComponent: () => import('./github-connect/github-connect.component').then((m) => m.GithubConnectComponent),
  },
  {
    path: 'gitlab',
    title: 'Integracja GitLab — TestGEN',
    loadComponent: () => import('./gitlab-connect/gitlab-connect.component').then((m) => m.GitlabConnectComponent),
  },
  {
    path: 'webhooks',
    title: 'Webhooki — TestGEN',
    loadComponent: () => import('./webhook-config/webhook-config.component').then((m) => m.WebhookConfigComponent),
  },
  {
    path: ':integrationId/sync',
    title: 'Synchronizacja z TMS — TestGEN',
    loadComponent: () => import('./sync-status/sync-status.component').then((m) => m.SyncStatusComponent),
  },
  {
    path: ':integrationId/history',
    title: 'Historia status checków — TestGEN',
    loadComponent: () => import('./status-history/status-history.component').then((m) => m.StatusHistoryComponent),
  },
  { path: '', pathMatch: 'full', redirectTo: 'github' },
];
