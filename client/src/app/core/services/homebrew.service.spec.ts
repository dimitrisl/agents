import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { HomebrewService } from './homebrew.service';
import { environment } from '../../../environments/environment';

describe('HomebrewService', () => {
  let service: HomebrewService;
  let httpTestingController: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        HomebrewService,
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });

    service = TestBed.inject(HomebrewService);
    httpTestingController = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTestingController.verify();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('exportHomebrewPdf should request blob with authenticated HTTP GET and trigger download', () => {
    const campaignName = 'Neverwinter';
    const mockBlob = new Blob(['%PDF-1.4 dummy content'], { type: 'application/pdf' });

    // Mock createObjectURL, revokeObjectURL and click
    const createObjectURLSpy = jest.fn().mockReturnValue('blob:http://localhost/mock-url');
    const revokeObjectURLSpy = jest.fn();
    window.URL.createObjectURL = createObjectURLSpy;
    window.URL.revokeObjectURL = revokeObjectURLSpy;

    const clickSpy = jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

    service.exportHomebrewPdf(campaignName);

    const req = httpTestingController.expectOne(`${environment.apiBaseUrl}/campaigns/${campaignName}/homebrew/export/pdf`);
    expect(req.request.method).toBe('GET');
    expect(req.request.responseType).toBe('blob');

    req.flush(mockBlob);

    expect(createObjectURLSpy).toHaveBeenCalledWith(mockBlob);
    expect(clickSpy).toHaveBeenCalled();
    expect(revokeObjectURLSpy).toHaveBeenCalledWith('blob:http://localhost/mock-url');

    clickSpy.mockRestore();
  });
});
