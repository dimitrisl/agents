import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { of, Subject, throwError } from 'rxjs';
import { AuthService } from '../../core/services/auth.service';
import { OAuthCallbackComponent } from './oauth-callback.component';

describe('OAuthCallbackComponent', () => {
  let authService: { exchangeDiscordCode: jest.Mock };
  let router: { navigate: jest.Mock };

  beforeEach(() => {
    authService = {
      exchangeDiscordCode: jest.fn(),
    };
    router = { navigate: jest.fn() };

    TestBed.configureTestingModule({
      imports: [OAuthCallbackComponent],
      providers: [
        { provide: AuthService, useValue: authService },
        { provide: Router, useValue: router },
      ],
    });
  });

  afterEach(() => {
    window.history.replaceState(null, '', '/');
  });

  it('shows error when fragment code is absent', () => {
    window.history.replaceState(null, '', '/auth/callback');
    const fixture = TestBed.createComponent(OAuthCallbackComponent);
    fixture.detectChanges();

    expect(fixture.componentInstance.errorMessage()).toContain('Missing Discord exchange code');
    expect(fixture.nativeElement.textContent).toContain('Missing Discord exchange code');
    expect(authService.exchangeDiscordCode).not.toHaveBeenCalled();
  });

  it('exchanges fragment code and navigates to /campaigns (or /settings if reset pending)', () => {
    window.history.replaceState(null, '', '/auth/callback#code=handoff-xyz');
    authService.exchangeDiscordCode.mockReturnValue(
      of({
        access_token: 'jwt',
        token_type: 'bearer',
        user: { id: 'd1', username: 'hero', must_change_password: false },
      })
    );

    const fixture = TestBed.createComponent(OAuthCallbackComponent);
    fixture.detectChanges();

    expect(authService.exchangeDiscordCode).toHaveBeenCalledWith('handoff-xyz');
    expect(router.navigate).toHaveBeenCalledWith(['/campaigns']);
    expect(window.location.hash).toBe('');
  });

  it('updates OnPush DOM asynchronously when exchange fails after detectChanges', () => {
    window.history.replaceState(null, '', '/auth/callback#code=bad-code');
    const exchange$ = new Subject<unknown>();
    authService.exchangeDiscordCode.mockReturnValue(exchange$);

    const fixture = TestBed.createComponent(OAuthCallbackComponent);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Completing Sign-In');

    exchange$.error({ error: { detail: 'Invalid or expired Discord login code.' } });
    fixture.detectChanges();

    expect(fixture.componentInstance.errorMessage()).toBe('Invalid or expired Discord login code.');
    expect(fixture.nativeElement.querySelector('[role="alert"]')?.textContent).toContain(
      'Invalid or expired Discord login code.'
    );
  });

  it('uses describeHttpError message on network outage without detail', () => {
    window.history.replaceState(null, '', '/auth/callback#code=net-down');
    authService.exchangeDiscordCode.mockReturnValue(
      throwError(() => new HttpErrorResponse({ status: 0, statusText: 'Unknown Error' }))
    );

    const fixture = TestBed.createComponent(OAuthCallbackComponent);
    fixture.detectChanges();

    expect(fixture.componentInstance.errorMessage()).toContain('Could not reach the Forge server');
  });
});
