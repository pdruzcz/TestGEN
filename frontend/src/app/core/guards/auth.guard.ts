import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';
import { firstValueFrom } from 'rxjs';

export const authGuard: CanActivateFn = async () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  // Already authenticated — allow
  if (authService.isAuthenticatedSignal()) {
    return true;
  }

  // Try to restore session from cookie-based auth (page refresh scenario)
  try {
    await firstValueFrom(authService.fetchProfile());
    if (authService.isAuthenticatedSignal()) {
      return true;
    }
  } catch {
    // Profile fetch failed — user not authenticated
  }

  return router.createUrlTree(['/login']);
};
