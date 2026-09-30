import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';
import { firstValueFrom } from 'rxjs';

export function roleGuard(...allowedRoles: string[]): CanActivateFn {
  return async () => {
    const authService = inject(AuthService);
    const router = inject(Router);

    // If user signal is null, try to restore session (handles page refresh race
    // where roleGuard runs before authGuard completes its async fetchProfile)
    if (!authService.currentUserSignal()) {
      try {
        await firstValueFrom(authService.fetchProfile());
      } catch {
        // Profile fetch failed — user not authenticated
        return router.createUrlTree(['/login']);
      }
    }

    const user = authService.currentUserSignal();
    if (!user) {
      return router.createUrlTree(['/login']);
    }
    if (allowedRoles.includes(user.role)) {
      return true;
    }

    return router.createUrlTree(['/403']);
  };
}
