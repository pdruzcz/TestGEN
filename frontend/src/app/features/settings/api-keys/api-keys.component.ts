import { Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { NavbarComponent } from '../../../shared/components/navbar.component';
import { FooterComponent } from '../../../shared/components/footer.component';
import { ApiKeyItem, ApiKeyScope, ApiKeyService } from '../../../core/services/api-key.service';

/** Maksymalny okres ważności klucza wymuszany też przez backend (Story 8.6, AC1). */
const MAX_EXPIRY_DAYS = 730;

@Component({
  selector: 'app-settings-api-keys',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterLink,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    NavbarComponent,
    FooterComponent,
  ],
  templateUrl: './api-keys.component.html',
  styleUrls: ['./api-keys.component.scss'],
})
export class ApiKeysComponent implements OnInit {
  private readonly destroyRef = inject(DestroyRef);
  private readonly apiKeyService = inject(ApiKeyService);

  readonly keys = this.apiKeyService.keysSignal;
  readonly isLoading = this.apiKeyService.isLoadingSignal;

  readonly isDialogOpen = signal(false);
  readonly isSubmitting = signal(false);
  readonly errorMessage = signal<string | null>(null);

  /** Klucz jawny — trzymany w pamięci tylko do zamknięcia okna (AC1). */
  readonly createdKey = signal<string | null>(null);
  readonly isKeyCopied = signal(false);

  readonly pendingRevokeId = signal<string | null>(null);

  readonly formName = signal('');
  readonly formScope = signal<ApiKeyScope>('read_only');
  readonly formExpiresAt = signal('');

  readonly maxExpiryDate = computed(() => {
    const max = new Date();
    max.setDate(max.getDate() + MAX_EXPIRY_DAYS);
    return max.toISOString().slice(0, 10);
  });

  readonly minExpiryDate = computed(() => {
    const min = new Date();
    min.setDate(min.getDate() + 1);
    return min.toISOString().slice(0, 10);
  });

  readonly isFormValid = computed(() => this.formName().trim().length > 0);

  ngOnInit(): void {
    this.reload();
  }

  openDialog(): void {
    this.formName.set('');
    this.formScope.set('read_only');
    this.formExpiresAt.set('');
    this.errorMessage.set(null);
    this.isDialogOpen.set(true);
  }

  closeDialog(): void {
    this.isDialogOpen.set(false);
    this.errorMessage.set(null);
  }

  submit(): void {
    if (!this.isFormValid() || this.isSubmitting()) {
      return;
    }
    this.isSubmitting.set(true);
    this.errorMessage.set(null);

    const expiresAt = this.formExpiresAt() ? new Date(`${this.formExpiresAt()}T23:59:59Z`).toISOString() : null;

    this.apiKeyService
      .createApiKey({
        name: this.formName().trim(),
        scope: this.formScope(),
        expiresAt,
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (response) => {
          this.isSubmitting.set(false);
          this.isDialogOpen.set(false);
          this.isKeyCopied.set(false);
          // Jedyna okazja na pokazanie klucza — backend go nie odda ponownie.
          this.createdKey.set(response.key);
          this.reload();
        },
        error: (err: { error?: { detail?: string } }) => {
          this.isSubmitting.set(false);
          this.errorMessage.set(err?.error?.detail ?? 'Nie udało się utworzyć klucza API.');
        },
      });
  }

  copyKey(): void {
    const key = this.createdKey();
    if (!key) {
      return;
    }
    void navigator.clipboard?.writeText(key).then(() => {
      this.isKeyCopied.set(true);
    });
  }

  dismissCreatedKey(): void {
    this.createdKey.set(null);
    this.isKeyCopied.set(false);
  }

  askRevoke(keyId: string): void {
    this.pendingRevokeId.set(keyId);
  }

  cancelRevoke(): void {
    this.pendingRevokeId.set(null);
  }

  confirmRevoke(): void {
    const keyId = this.pendingRevokeId();
    if (!keyId) {
      return;
    }
    this.apiKeyService
      .revokeApiKey(keyId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.pendingRevokeId.set(null);
          this.reload();
        },
        error: () => {
          this.pendingRevokeId.set(null);
          this.errorMessage.set('Nie udało się odwołać klucza API.');
        },
      });
  }

  scopeLabel(scope: ApiKeyScope): string {
    return scope === 'full_access' ? 'Pełny dostęp' : 'Tylko odczyt';
  }

  statusLabel(key: ApiKeyItem): string {
    switch (key.status) {
      case 'revoked':
        return 'Odwołany';
      case 'expired':
        return 'Wygasły';
      default:
        return 'Aktywny';
    }
  }

  private reload(): void {
    this.apiKeyService.list().pipe(takeUntilDestroyed(this.destroyRef)).subscribe();
  }
}
