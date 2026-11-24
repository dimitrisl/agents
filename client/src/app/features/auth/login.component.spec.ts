import { TestBed } from '@angular/core/testing';
import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, Router, convertToParamMap } from '@angular/router';
import { of, Subject } from 'rxjs';
import { AuthService } from '../../core/services/auth.service';
import { LoginComponent } from './login.component';

describe('LoginComponent submit state', () => {
  let component: LoginComponent;
  let login$: Subject<unknown>;
  let auth: { login: jest.Mock; register: jest.Mock; getProviders: jest.Mock; startDiscordLogin: jest.Mock };
  let router: { navigate: jest.Mock };
  let oauthErrorParam: string | null;

  beforeEach(() => {
    oauthErrorParam = null;
    login$ = new Subject();
    auth = {
      login: jest.fn(() => login$),
      register: jest.fn(),
      getProviders: jest.fn(() => of({ local: true, discord: false })),
      startDiscordLogin: jest.fn(),
    };
    router = { navigate: jest.fn() };
    TestBed.configureTestingModule({
      imports: [LoginComponent],
      providers: [
        { provide: AuthService, useValue: auth },
        { provide: Router, useValue: router },
        {
          provide: ActivatedRoute,
          useValue: {
            get snapshot() {
              return { queryParamMap: convertToParamMap(oauthErrorParam ? { oauth_error: oauthErrorParam } : {}) };
            },
          },
        },
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

  it('redirects to /settings when user has must_change_password enabled', () => {
    component.onSubmit();
    login$.next({
      access_token: 'temp-jwt',
      token_type: 'bearer',
      user: { id: 'u1', username: 'edrann', must_change_password: true },
    });
    expect(router.navigate).toHaveBeenCalledWith(['/settings']);
  });

  it('exposes discordEnabled only when backend providers enable discord', () => {
    auth.getProviders.mockReturnValue(of({ local: true, discord: true }));
    component.ngOnInit();
    expect(component.discordEnabled).toBe(true);
  });

  it('opens auth form with oauth_error, scrubs query param, and guards Discord double click', () => {
    oauthErrorParam = 'Discord authorization was cancelled.';
    component.ngOnInit();

    expect(component.mode).toBe('auth');
    expect(component.error).toBe('Discord authorization was cancelled.');
    expect(router.navigate).toHaveBeenCalledWith(
      [],
      expect.objectContaining({ replaceUrl: true, queryParams: { oauth_error: null } })
    );

    component.onDiscordLogin();
    component.onDiscordLogin();
    component.onSubmit();
    expect(component.submitting).toBe(false);
    expect(component.discordSubmitting).toBe(true);
    expect(auth.startDiscordLogin).toHaveBeenCalledTimes(1);
    expect(auth.login).not.toHaveBeenCalled();

    component.onPageShow();
    expect(component.discordSubmitting).toBe(false);
  });
});
