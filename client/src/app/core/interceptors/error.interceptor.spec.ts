import { TestBed } from '@angular/core/testing';
import { HttpClient, HttpContext, HttpErrorResponse, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { RollToastService } from '../services/roll-toast.service';
import { AuthService } from '../services/auth.service';
import { SILENT_HTTP_ERRORS, errorInterceptor, isReportedGlobally } from './error.interceptor';

describe('errorInterceptor', () => {
  let http: HttpClient;
  let httpMock: HttpTestingController;
  let toast: { showMessage: jest.Mock };
  let auth: { logout: jest.Mock };

  beforeEach(() => {
    toast = { showMessage: jest.fn() };
    auth = { logout: jest.fn() };
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([errorInterceptor])),
        provideHttpClientTesting(),
        { provide: RollToastService, useValue: toast },
        { provide: AuthService, useValue: auth },
      ],
    });
    http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  function fail(status: number, body: unknown = null, context?: HttpContext) {
    let received: unknown;
    http.get('/api/v1/thing', { context }).subscribe({ error: (e) => (received = e) });
    httpMock.expectOne('/api/v1/thing').flush(body, { status, statusText: 'x' });
    return received;
  }

  it('announces server errors with the API detail and still re-throws', () => {
    const err = fail(500, { detail: 'Database unavailable' });
    expect(toast.showMessage).toHaveBeenCalledWith('⚠️ SERVER ERROR', 'Database unavailable');
    expect(err).toBeInstanceOf(HttpErrorResponse);
  });

  it('announces rate limits', () => {
    fail(429);
    expect(toast.showMessage).toHaveBeenCalledWith('🐢 SLOW DOWN', expect.any(String));
  });

  it('announces a lost connection', () => {
    http.get('/api/v1/thing').subscribe({ error: () => {} });
    httpMock.expectOne('/api/v1/thing').error(new ProgressEvent('error'), { status: 0 });
    expect(toast.showMessage).toHaveBeenCalledWith('📡 CONNECTION LOST', expect.any(String));
  });

  it.each([400, 403, 404, 409, 422])('leaves %i to the caller', (status) => {
    const err = fail(status, { detail: 'nope' });
    expect(toast.showMessage).not.toHaveBeenCalled();
    expect(auth.logout).not.toHaveBeenCalled();
    expect(isReportedGlobally(err)).toBe(false);
  });

  it('logs out and toasts globally on 401 outside auth endpoints', () => {
    const err = fail(401, { detail: 'Invalid token' });
    expect(auth.logout).toHaveBeenCalledTimes(1);
    expect(toast.showMessage).toHaveBeenCalledWith('🔒 SESSION EXPIRED', expect.any(String));
    expect(isReportedGlobally(err)).toBe(true);
  });

  it('does not logout on 401 from /auth/login or /auth/register', () => {
    http.post('/api/v1/auth/login', {}).subscribe({ error: () => {} });
    httpMock.expectOne('/api/v1/auth/login').flush({ detail: 'Bad creds' }, { status: 401, statusText: 'Unauthorized' });
    expect(auth.logout).not.toHaveBeenCalled();
    expect(toast.showMessage).not.toHaveBeenCalled();
  });

  it('stays quiet for requests marked SILENT_HTTP_ERRORS', () => {
    fail(503, null, new HttpContext().set(SILENT_HTTP_ERRORS, true));
    expect(toast.showMessage).not.toHaveBeenCalled();
  });

  it('tells callers when the user was already told', () => {
    expect(isReportedGlobally(fail(502))).toBe(true);
  });
});
