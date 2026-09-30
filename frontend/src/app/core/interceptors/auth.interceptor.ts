import {
  HttpInterceptorFn,
  HttpRequest,
  HttpHandlerFn,
  HttpErrorResponse,
} from "@angular/common/http";
import { inject } from "@angular/core";
import { Router } from "@angular/router";
import {
  catchError,
  switchMap,
  throwError,
  Observable,
  BehaviorSubject,
  filter,
  take,
  timeout,
} from "rxjs";
import { AuthService } from "../services/auth.service";
import { environment } from "../../../environments/environment";

let isRefreshing = false;
const refreshSubject = new BehaviorSubject<boolean | null>(null);

/** Default timeout for API requests (30 seconds). */
const API_TIMEOUT_MS = 30_000;

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const authService = inject(AuthService);
  const router = inject(Router);
  const user = authService.currentUserSignal();

  // Only add credentials and headers for API requests
  const isApiRequest = req.url.includes("/api/");
  if (isApiRequest) {
    const headers: Record<string, string> = {};

    // Add tenant ID header for multi-tenant context
    if (user?.tenantId) {
      headers["X-TestGEN-Tenant-Id"] = user.tenantId;
    }

    req = req.clone({
      setHeaders: headers,
      withCredentials: true,
    });
  }

  // M6: timeout on all API requests to prevent indefinite hangs.
  // Split into branches instead of conditional spread — TS cannot preserve
  // tuple type across `...(cond ? [op] : [])`, which breaks pipe() typing.
  const baseRequest$ = next(req);
  const request$ = isApiRequest
    ? baseRequest$.pipe(timeout(API_TIMEOUT_MS))
    : baseRequest$;

  return request$.pipe(
    catchError((error: HttpErrorResponse) => {
      // M7: Only attempt refresh for token-expired 401s, not login failures
      if (
        error.status === 401 &&
        isApiRequest &&
        !req.url.includes("/auth/refresh") &&
        !req.url.includes("/auth/login") &&
        !req.url.includes("/auth/logout") &&
        !req.url.includes("/auth/select-tenant")
      ) {
        return handleRefresh(req, next, authService, router);
      }
      return throwError(() => error);
    }),
  );
};

function handleRefresh(
  req: HttpRequest<unknown>,
  next: HttpHandlerFn,
  authService: AuthService,
  router: Router,
): Observable<any> {
  if (isRefreshing) {
    // H3 fix: Use BehaviorSubject + filter(non-null) to prevent race.
    // Queued requests wait for refresh result, then retry or fail.
    return refreshSubject.pipe(
      filter((success): success is boolean => success !== null),
      take(1),
      switchMap((success) => {
        if (success) {
          return next(req);
        }
        return throwError(() => new HttpErrorResponse({ status: 401 }));
      }),
    );
  }

  isRefreshing = true;
  // Reset subject so queued requests don't get stale values
  refreshSubject.next(null);

  return authService.refreshToken().pipe(
    switchMap(() => {
      isRefreshing = false;
      refreshSubject.next(true);
      return next(req);
    }),
    catchError((refreshError) => {
      isRefreshing = false;
      refreshSubject.next(false);
      authService.logout();
      return throwError(() => refreshError);
    }),
  );
}
