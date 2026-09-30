import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { LoginComponent } from './login.component';

@Component({ template: '', standalone: true })
class DummyComponent {}

describe('LoginComponent', () => {
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [LoginComponent],
      providers: [
        provideRouter([
          { path: 'login', component: DummyComponent },
          { path: 'mfa-verify', component: DummyComponent },
          { path: 'register', component: DummyComponent },
          { path: 'reset-password', component: DummyComponent },
          { path: '', component: DummyComponent },
          { path: '**', component: DummyComponent },
        ]),
        provideHttpClient(),
        provideHttpClientTesting(),
        provideAnimationsAsync(),
      ],
    }).compileComponents();

    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    // Flush any outstanding requests to avoid verify errors
    httpMock
      .match(() => true)
      .forEach((r) => {
        try {
          r.flush({});
        } catch {
          // already resolved
        }
      });
  });

  it('should create', () => {
    const fixture = TestBed.createComponent(LoginComponent);
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('should have email and password form controls', () => {
    const fixture = TestBed.createComponent(LoginComponent);
    const component = fixture.componentInstance;
    expect(component.form.controls.email).toBeTruthy();
    expect(component.form.controls.password).toBeTruthy();
  });

  it('should be invalid when empty', () => {
    const fixture = TestBed.createComponent(LoginComponent);
    expect(fixture.componentInstance.form.valid).toBe(false);
  });

  it('should be valid with email and password', () => {
    const fixture = TestBed.createComponent(LoginComponent);
    const component = fixture.componentInstance;
    component.form.controls.email.setValue('test@test.com');
    component.form.controls.password.setValue('password123');
    expect(component.form.valid).toBe(true);
  });

  it('should not submit when form is invalid', () => {
    const fixture = TestBed.createComponent(LoginComponent);
    const component = fixture.componentInstance;
    component.onSubmit();
    expect(component.isSubmitting()).toBe(false);
  });

  it('should send POST to /auth/login on valid submit', () => {
    const fixture = TestBed.createComponent(LoginComponent);
    const component = fixture.componentInstance;
    component.form.controls.email.setValue('test@test.com');
    component.form.controls.password.setValue('password123');

    component.onSubmit();
    expect(component.isSubmitting()).toBe(true);

    const req = httpMock.expectOne('/api/v1/auth/login');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({
      email: 'test@test.com',
      password: 'password123',
    });

    // Flush login response — this triggers fetchProfile internally
    req.flush({
      message: 'Login successful',
      mfaRequired: false,
      mfaToken: null,
    });

    // Flush the fetchProfile request that follows
    const profileReqs = httpMock.match('/api/v1/users/me');
    profileReqs.forEach((r) =>
      r.flush({
        id: '1',
        tenantId: 't1',
        email: 'test@test.com',
        name: 'Test',
        role: 'owner',
        isActive: true,
        emailVerifiedAt: null,
        notificationPreferences: {},
      }),
    );
  });

  it('should show error on 401', () => {
    const fixture = TestBed.createComponent(LoginComponent);
    const component = fixture.componentInstance;
    component.form.controls.email.setValue('test@test.com');
    component.form.controls.password.setValue('wrongpassword');

    component.onSubmit();

    const req = httpMock.expectOne('/api/v1/auth/login');
    req.flush({ detail: 'Invalid credentials' }, { status: 401, statusText: 'Unauthorized' });

    expect(component.errorMessage()).toBe('Nieprawidłowy email lub hasło');
    expect(component.isSubmitting()).toBe(false);
  });

  it('should toggle password visibility', () => {
    const fixture = TestBed.createComponent(LoginComponent);
    const component = fixture.componentInstance;
    expect(component.hidePassword()).toBe(true);
    component.hidePassword.set(false);
    expect(component.hidePassword()).toBe(false);
  });
});
