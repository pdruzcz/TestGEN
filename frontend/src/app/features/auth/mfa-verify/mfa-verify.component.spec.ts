import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { MfaVerifyComponent } from './mfa-verify.component';

describe('MfaVerifyComponent', () => {
  let router: Router;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MfaVerifyComponent],
      providers: [
        provideRouter([
          { path: 'mfa-verify', component: MfaVerifyComponent },
          { path: 'login', component: MfaVerifyComponent },
        ]),
        provideHttpClient(),
        provideHttpClientTesting(),
        provideAnimationsAsync(),
      ],
    }).compileComponents();

    router = TestBed.inject(Router);
  });

  it('should create', () => {
    const fixture = TestBed.createComponent(MfaVerifyComponent);
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('should have code form control', () => {
    const fixture = TestBed.createComponent(MfaVerifyComponent);
    expect(fixture.componentInstance.form.controls.code).toBeTruthy();
  });

  it('should toggle backup code mode', () => {
    const fixture = TestBed.createComponent(MfaVerifyComponent);
    const component = fixture.componentInstance;
    expect(component.useBackupCode()).toBe(false);
    component.toggleBackupCode();
    expect(component.useBackupCode()).toBe(true);
    component.toggleBackupCode();
    expect(component.useBackupCode()).toBe(false);
  });

  it('should not submit when form is invalid', () => {
    const fixture = TestBed.createComponent(MfaVerifyComponent);
    const component = fixture.componentInstance;
    component.onSubmit();
    expect(component.isSubmitting()).toBe(false);
  });
});
