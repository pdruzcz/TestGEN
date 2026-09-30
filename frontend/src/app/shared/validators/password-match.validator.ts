import { AbstractControl, ValidationErrors } from '@angular/forms';

/**
 * Cross-field validator: ensures two password fields match.
 * @param passwordKey - form control name for the password field
 * @param confirmKey - form control name for the confirmation field
 */
export function passwordMatchValidator(
  passwordKey = 'password',
  confirmKey = 'confirmPassword',
): (control: AbstractControl) => ValidationErrors | null {
  return (control: AbstractControl): ValidationErrors | null => {
    const password = control.get(passwordKey);
    const confirm = control.get(confirmKey);
    if (password && confirm && password.value !== confirm.value) {
      return { passwordMismatch: true };
    }
    return null;
  };
}
