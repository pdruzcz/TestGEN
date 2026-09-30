import { HttpClient, HttpParams, HttpResponse } from "@angular/common/http";
import { Injectable, inject, signal } from "@angular/core";
import { Observable, map, tap } from "rxjs";
import { environment } from "../../../../environments/environment";

export interface UserItem {
  id: string;
  email: string;
  name: string;
  role: "owner" | "admin" | "user";
  isActive: boolean;
  mfaEnabled: boolean;
  createdAt: string | null;
}

export interface UserListResponse {
  users: UserItem[];
  total: number;
}

@Injectable({ providedIn: "root" })
export class UserManagementService {
  private readonly apiUrl = `${environment.apiUrl}/users`;
  private readonly http = inject(HttpClient);

  readonly usersSignal = signal<UserItem[]>([]);
  readonly totalSignal = signal(0);
  readonly isLoadingSignal = signal(false);

  list(page = 1, pageSize = 50): Observable<UserListResponse> {
    const params = new HttpParams()
      .set("page", String(page))
      .set("page_size", String(pageSize));

    this.isLoadingSignal.set(true);
    return this.http
      .get<UserListResponse>(this.apiUrl, { params, observe: "response" })
      .pipe(
        map((resp: HttpResponse<UserListResponse>) => {
          const body = resp.body ?? { users: [], total: 0 };
          const headerTotal = Number(
            resp.headers.get("X-Total-Count") ?? body.total,
          );
          return {
            users: body.users ?? [],
            total: Number.isFinite(headerTotal) ? headerTotal : body.total,
          };
        }),
        tap({
          next: (result) => {
            this.usersSignal.set(result.users);
            this.totalSignal.set(result.total);
            this.isLoadingSignal.set(false);
          },
          error: () => this.isLoadingSignal.set(false),
        }),
      );
  }

  updateRole(userId: string, role: string): Observable<UserItem> {
    return this.http.put<UserItem>(`${this.apiUrl}/${userId}/role`, { role });
  }

  deleteUser(userId: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${userId}`);
  }
}
