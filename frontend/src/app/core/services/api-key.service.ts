import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';
import { environment } from '../../../environments/environment';

export type ApiKeyScope = 'read_only' | 'full_access';
export type ApiKeyStatus = 'active' | 'expired' | 'revoked';

export interface ApiKeyItem {
  id: string;
  name: string;
  scope: ApiKeyScope;
  keyPrefix: string;
  status: ApiKeyStatus;
  expiresAt: string | null;
  lastUsedAt: string | null;
  revokedAt: string | null;
  createdAt: string;
}

export interface ApiKeyListResponse {
  items: ApiKeyItem[];
  total: number;
}

/** Odpowiedź tworzenia — `key` to jedyny moment, w którym backend oddaje klucz jawnie. */
export interface CreateApiKeyResponse {
  key: string;
  apiKey: ApiKeyItem;
}

export interface CreateApiKeyPayload {
  name: string;
  scope: ApiKeyScope;
  expiresAt?: string | null;
}

@Injectable({ providedIn: 'root' })
export class ApiKeyService {
  private readonly apiUrl = `${environment.apiUrl}/api-keys`;
  private readonly http = inject(HttpClient);

  readonly keysSignal = signal<ApiKeyItem[]>([]);
  readonly isLoadingSignal = signal(false);

  list(): Observable<ApiKeyListResponse> {
    this.isLoadingSignal.set(true);
    return this.http.get<ApiKeyListResponse>(this.apiUrl).pipe(
      tap({
        next: (result) => {
          this.keysSignal.set(result.items ?? []);
          this.isLoadingSignal.set(false);
        },
        error: () => this.isLoadingSignal.set(false),
      }),
    );
  }

  createApiKey(payload: CreateApiKeyPayload): Observable<CreateApiKeyResponse> {
    return this.http.post<CreateApiKeyResponse>(this.apiUrl, {
      name: payload.name,
      scope: payload.scope,
      expiresAt: payload.expiresAt ?? null,
    });
  }

  revokeApiKey(keyId: string): Observable<ApiKeyItem> {
    return this.http.delete<ApiKeyItem>(`${this.apiUrl}/${keyId}`);
  }
}
