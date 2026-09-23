import { TestBed } from '@angular/core/testing';
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { jwtInterceptor } from './jwt.interceptor';
import { AuthService } from '../services/auth.service';

describe('jwtInterceptor', () => {
  let authServiceSpy: jest.Mocked<AuthService>;
  let http: HttpClient;
  let httpTestingController: HttpTestingController;

  beforeEach(() => {
    authServiceSpy = {
      token: jest.fn(),
    } as unknown as jest.Mocked<AuthService>;

    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([jwtInterceptor])),
        provideHttpClientTesting(),
        { provide: AuthService, useValue: authServiceSpy },
      ],
    });

    http = TestBed.inject(HttpClient);
    httpTestingController = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTestingController.verify();
  });

  it('should add Authorization header if token exists and URL contains /api/v1/', () => {
    authServiceSpy.token.mockReturnValue('my-secret-token');

    http.get('/api/v1/protected-data').subscribe();

    const req = httpTestingController.expectOne('/api/v1/protected-data');
    expect(req.request.headers.get('Authorization')).toBe('Bearer my-secret-token');
    req.flush({});
  });

  it('should not add Authorization header if URL does not contain /api/v1/', () => {
    authServiceSpy.token.mockReturnValue('my-secret-token');

    http.get('/assets/images/logo.png').subscribe();

    const req = httpTestingController.expectOne('/assets/images/logo.png');
    expect(req.request.headers.has('Authorization')).toBe(false);
    req.flush({});
  });

  it('should not add Authorization header if token does not exist', () => {
    authServiceSpy.token.mockReturnValue(null);

    http.get('/api/v1/protected-data').subscribe();

    const req = httpTestingController.expectOne('/api/v1/protected-data');
    expect(req.request.headers.has('Authorization')).toBe(false);
    req.flush({});
  });
});
