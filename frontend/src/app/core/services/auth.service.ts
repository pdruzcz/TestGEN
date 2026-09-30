import { Injectable, inject, signal, computed } from "@angular/core";
import { HttpClient } from "@angular/common/http";
import { Router } from "@angular/router";
import { Observable, tap, finalize, shareReplay } from "rxjs";
import { environment } from "../../../environments/environment";

export interface UserProfile {
  id: string;
  tenantId: string;
  email: string;
  name: string;
  role: string;
  isActive: boolean;
  emailVerifiedAt: string | null;
  notificationPreferences: Record<string, unknown>;
  mfaEnabled: boolean;
}

export interface RegisterPayload {
  email: string;
  password: string;
  companyName: string;
  nip?: string;
}

export interface RegisterResponse {
  email: string;
  message: string;
}

export interface TenantInfo {
  tenantId: string;
  tenantName: string;
  role: string;
}

export interface LoginResponse {
  message: string;
  mfaRequired: boolean;
  mfaToken: string | null;
  tenantsRequired: boolean;
  preAuthToken: string | null;
  tenants: TenantInfo[] | null;
}

export interface MfaSetupResponse {
  secret: string;
  provisioningUri: string;
}

export interface MfaConfirmResponse {
  backupCodes: string[];
  message: string;
}

@Injectable({ providedIn: "root" })
export class AuthService {
  private readonly apiUrl = environment.apiUrl;
  private _profileRequest$: Observable<UserProfile> | null = null;

  readonly currentUserSignal = signal<UserProfile | null>(null);
  readonly isLoadingSignal = signal(false);
  readonly isAuthenticatedSignal = computed(() => !!this.currentUserSignal());

  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);

  /** Update user profile signal (encapsulated mutation point). */
  updateCurrentUser(user: UserProfile): void {
    this.currentUserSignal.set(user);
  }

  register(payload: RegisterPayload): Observable<RegisterResponse> {
    return this.http.post<RegisterResponse>(
      `${this.apiUrl}/auth/register`,
      payload,
    );
  }

  verifyEmail(token: string): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(
      `${this.apiUrl}/auth/verify-email`,
      { token },
    );
  }

  acceptInvitation(
    token: string,
    password: string,
  ): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(
      `${this.apiUrl}/auth/accept-invitation`,
      { token, password },
    );
  }

  resetPasswordByToken(
    token: string,
    newPassword: string,
  ): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(
      `${this.apiUrl}/users/reset-password-token`,
      { token, newPassword },
    );
  }

  login(email: string, password: string): Observable<LoginResponse> {
    return this.http.post<LoginResponse>(`${this.apiUrl}/auth/login`, {
      email,
      password,
    });
  }

  selectTenant(
    preAuthToken: string,
    tenantId: string,
  ): Observable<LoginResponse> {
    return this.http.post<LoginResponse>(`${this.apiUrl}/auth/select-tenant`, {
      preAuthToken,
      tenantId,
    });
  }

  verifyMfa(mfaToken: string, code: string): Observable<LoginResponse> {
    return this.http.post<LoginResponse>(`${this.apiUrl}/auth/mfa/verify`, {
      mfaToken,
      code,
    });
  }

  refreshToken(): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(
      `${this.apiUrl}/auth/refresh`,
      {},
    );
  }

  logout(): void {
    this.currentUserSignal.set(null);
    this._profileRequest$ = null;
    this.http.post(`${this.apiUrl}/auth/logout`, {}).subscribe({
      next: () => this.router.navigateByUrl("/login"),
      error: () => this.router.navigateByUrl("/login"),
    });
  }

  setupMfa(): Observable<MfaSetupResponse> {
    return this.http.post<MfaSetupResponse>(
      `${this.apiUrl}/auth/mfa/setup`,
      {},
    );
  }

  confirmMfa(code: string): Observable<MfaConfirmResponse> {
    return this.http.post<MfaConfirmResponse>(
      `${this.apiUrl}/auth/mfa/confirm`,
      { code },
    );
  }

  disableMfa(password: string): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiUrl}/auth/mfa`, {
      body: { password },
    });
  }

  regenerateBackupCodes(password: string): Observable<MfaConfirmResponse> {
    return this.http.post<MfaConfirmResponse>(
      `${this.apiUrl}/auth/mfa/backup-codes`,
      { password },
    );
  }

  fetchProfile(): Observable<UserProfile> {
    // Dedup concurrent calls (e.g. authGuard + roleGuard both trigger on page refresh)
    if (this._profileRequest$) {
      return this._profileRequest$;
    }
    this.isLoadingSignal.set(true);
    this._profileRequest$ = this.http
      .get<UserProfile>(`${this.apiUrl}/users/me`)
      .pipe(
        tap((user) => this.currentUserSignal.set(user)),
        finalize(() => {
          this.isLoadingSignal.set(false);
          this._profileRequest$ = null;
        }),
        shareReplay(1),
      );
    return this._profileRequest$;
  }
}
