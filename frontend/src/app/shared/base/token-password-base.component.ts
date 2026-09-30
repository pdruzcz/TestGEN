import { DestroyRef, Directive, inject, OnInit, signal } from "@angular/core";
import { ActivatedRoute } from "@angular/router";
import { FormGroup, FormControl, Validators } from "@angular/forms";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { HttpErrorResponse } from "@angular/common/http";
import { Observable } from "rxjs";
import { AuthService } from "../../core/services/auth.service";
import { ApiErrorResponse } from "../models/api-error.model";
import { passwordComplexityValidator } from "../validators/password-complexity.validator";
import { passwordMatchValidator } from "../validators/password-match.validator";

interface TokenPasswordForm {
  password: FormControl<string>;
  confirmPassword: FormControl<string>;
}

/**
 * Abstract base class for token-based password forms (set-password, reset-password).
 * Encapsulates shared logic: token validation, form setup, submission flow.
 * Subclasses provide config (messages) and the auth service call.
 */
@Directive()
export abstract class TokenPasswordBaseComponent implements OnInit {
  isSubmitting = signal(false);
  successMessage = signal("");
  serverError = signal("");
  tokenError = signal("");

  protected token = "";

  form = new FormGroup<TokenPasswordForm>(
    {
      password: new FormControl("", {
        nonNullable: true,
        validators: [
          Validators.required,
          Validators.minLength(12),
          Validators.maxLength(128),
          passwordComplexityValidator,
        ],
      }),
      confirmPassword: new FormControl("", {
        nonNullable: true,
        validators: [Validators.required, Validators.maxLength(128)],
      }),
    },
    { validators: passwordMatchValidator("password", "confirmPassword") },
  );

  /** Error message shown when token is missing from URL. */
  protected abstract get missingTokenMessage(): string;

  /** Default success message when server doesn't provide one. */
  protected abstract get defaultSuccessMessage(): string;

  /** Default error message on submission failure. */
  protected abstract get defaultErrorMessage(): string;

  /** Auth service call to execute on form submission. */
  protected abstract callAuthService(
    token: string,
    password: string,
  ): Observable<{ message: string }>;

  protected route = inject(ActivatedRoute);
  protected authService = inject(AuthService);
  protected destroyRef = inject(DestroyRef);

  ngOnInit(): void {
    this.token = this.route.snapshot.queryParamMap.get("token") || "";
    if (!this.token) {
      this.tokenError.set(this.missingTokenMessage);
    } else if (!/^[a-f0-9]{1,64}$/i.test(this.token)) {
      this.tokenError.set("Nieprawidłowy format tokena");
      this.token = "";
    }
  }

  onSubmit(): void {
    if (this.form.invalid || this.isSubmitting() || !this.token) return;

    this.isSubmitting.set(true);
    this.serverError.set("");

    this.callAuthService(this.token, this.form.controls.password.value)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.isSubmitting.set(false);
          this.successMessage.set(res.message || this.defaultSuccessMessage);
        },
        error: (err: HttpErrorResponse) => {
          this.isSubmitting.set(false);
          const body = err.error as ApiErrorResponse | null;
          this.serverError.set(this.defaultErrorMessage);
        },
      });
  }
}
