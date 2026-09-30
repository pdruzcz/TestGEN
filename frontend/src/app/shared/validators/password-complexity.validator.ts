import { AbstractControl, ValidationErrors } from '@angular/forms';

export function passwordComplexityValidator(control: AbstractControl): ValidationErrors | null {
  const value = control.value as string;
  if (!value) return null;

  const errors: string[] = [];
  if (!/[A-Z]/.test(value)) errors.push('wielka litera');
  if (!/[a-z]/.test(value)) errors.push('mała litera');
  if (!/\d/.test(value)) errors.push('cyfra');
  if (!/[^A-Za-z0-9]/.test(value)) errors.push('znak specjalny');

  return errors.length ? { passwordComplexity: `Brak: ${errors.join(', ')}` } : null;
}
