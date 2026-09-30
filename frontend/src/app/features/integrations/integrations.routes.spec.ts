import { INTEGRATIONS_ROUTES } from './integrations.routes';

/**
 * Bezpiecznik na trasy integracji.
 *
 * Powód istnienia: w Story 8.2 trasa `/gitlab` nie została zarejestrowana,
 * a mimo to testy komponentu przechodziły — spec instancjonuje komponent
 * bezpośrednio, z pominięciem routingu. Link w menu prowadził donikąd.
 */
describe('INTEGRATIONS_ROUTES', () => {
  function paths(): string[] {
    return INTEGRATIONS_ROUTES.map((route) => route.path ?? '');
  }

  it('rejestruje ekran GitHuba', () => {
    expect(paths()).toContain('github');
  });

  it('rejestruje ekran GitLaba', () => {
    expect(paths()).toContain('gitlab');
  });

  it('rejestruje ekran webhooków wychodzących', () => {
    expect(paths()).toContain('webhooks');
  });

  it('rejestruje historię status checków per integracja', () => {
    expect(paths()).toContain(':integrationId/history');
  });

  it('rejestruje ekran synchronizacji z TMS', () => {
    expect(paths()).toContain(':integrationId/sync');
  });

  it('przekierowuje pusty segment na GitHuba', () => {
    const fallback = INTEGRATIONS_ROUTES.find((route) => route.path === '');

    expect(fallback?.redirectTo).toBe('github');
    expect(fallback?.pathMatch).toBe('full');
  });

  it('każda trasa ekranu ma tytuł i leniwy komponent', () => {
    for (const route of INTEGRATIONS_ROUTES.filter((r) => r.path)) {
      expect(route.title).toBeTruthy();
      expect(route.loadComponent).toBeTypeOf('function');
    }
  });

  it('przekierowanie jest ostatnie — inaczej przesłoniłoby konkretne ścieżki', () => {
    expect(INTEGRATIONS_ROUTES.at(-1)?.path).toBe('');
  });

  it('trasa z parametrem jest po trasach stałych', () => {
    // Inaczej ':integrationId' połknąłby 'github', 'gitlab' i 'webhooks'.
    for (const param of [':integrationId/sync', ':integrationId/history']) {
      const paramIndex = paths().indexOf(param);
      for (const fixed of ['github', 'gitlab', 'webhooks']) {
        expect(paths().indexOf(fixed)).toBeLessThan(paramIndex);
      }
    }
  });
});
