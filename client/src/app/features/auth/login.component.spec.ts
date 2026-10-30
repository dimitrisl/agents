import { TestBed } from '@angular/core/testing';
import { HttpErrorResponse } from '@angular/common/http';
import { Router } from '@angular/router';
import { Subject } from 'rxjs';
import { AuthService } from '../../core/services/auth.service';
import { LoginComponent } from './login.component';

describe('LoginComponent submit state', () => {
  let component: LoginComponent;
  let login$: Subject<unknown>;
  let auth: { login: jest.Mock; register: jest.Mock };

  beforeEach(() => {
    login$ = new Subject();
    auth = { login: jest.fn(() => login$), register: jest.fn() };
    TestBed.configureTestingModule({
      imports: [LoginComponent],
      providers: [
        { provide: AuthService, useValue: auth },
        { provide: Router, useValue: { navigate: jest.fn() } },
      ],
    });
    component = TestBed.createComponent(LoginComponent).componentInstance;
    component.username = 'edrann';
    component.password = 'secret';
  });

  it('blocks a second submit while the first is running', () => {
    component.onSubmit();
    component.onSubmit();
    expect(component.submitting).toBe(true);
    expect(auth.login).toHaveBeenCalledTimes(1);
  });

  it('says the server is unreachable instead of "invalid password" when offline', () => {
    component.onSubmit();
    login$.error(new HttpErrorResponse({ status: 0 }));
    expect(component.submitting).toBe(false);
    expect(component.error).toContain('Could not reach');
  });

  it('shows the API detail for wrong credentials', () => {
    component.onSubmit();
    login$.error(new HttpErrorResponse({ status: 401, error: { detail: 'Incorrect username or password' } }));
    expect(component.error).toBe('Incorrect username or password');
  });
});
