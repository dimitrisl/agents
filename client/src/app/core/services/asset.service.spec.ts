import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { AssetService } from './asset.service';

describe('AssetService', () => {
  let service: AssetService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [AssetService],
    });
    service = TestBed.inject(AssetService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
  });

  it('recognizes internal campaign asset URLs and rejects third-party lookalikes', () => {
    expect(service.isProtectedCampaignAssetUrl('/api/v1/campaigns/Vault/assets/abc.png')).toBe(true);
    expect(service.isProtectedCampaignAssetUrl('https://evil.example/api/v1/campaigns/Vault/assets/abc.png')).toBe(false);
    expect(service.isProtectedCampaignAssetUrl('https://cdn.example.com/dragon.png')).toBe(false);
    expect(service.isProtectedCampaignAssetUrl('')).toBe(false);
  });

  it('uploads asset with requested kind and encoded campaign name', () => {
    const file = new File(['png'], 'scene.png', { type: 'image/png' });
    let resultUrl = '';
    service.uploadAsset('Dark Sun', file, 'scene').subscribe((res) => {
      resultUrl = res.url;
    });

    const req = http.expectOne((r) => r.method === 'POST' && r.url.endsWith('/campaigns/Dark%20Sun/assets'));
    expect(req.request.body instanceof FormData).toBe(true);
    expect((req.request.body as FormData).get('kind')).toBe('scene');
    req.flush({ url: '/api/v1/campaigns/Dark%20Sun/assets/abc.png', kind: 'scene' });
    expect(resultUrl).toBe('/api/v1/campaigns/Dark%20Sun/assets/abc.png');
  });

  it('returns external URLs directly without HTTP blob fetch and fetches blobs for internal assets', () => {
    let directResult: any = null;
    service.resolveDisplayImage('https://cdn.example.com/dragon.png').subscribe((res) => {
      directResult = res;
    });
    expect(directResult).toEqual({ src: 'https://cdn.example.com/dragon.png', isObjectUrl: false });

    const origCreate = URL.createObjectURL;
    (URL as any).createObjectURL = jest.fn(() => 'blob:mock-asset');
    try {
      let protectedResult: any = null;
      service.resolveDisplayImage('/api/v1/campaigns/Vault/assets/abc.png').subscribe((res) => {
        protectedResult = res;
      });
      const req = http.expectOne((r) => r.method === 'GET' && r.url.endsWith('/campaigns/Vault/assets/abc.png'));
      expect(req.request.responseType).toBe('blob');
      req.flush(new Blob(['img'], { type: 'image/png' }));
      expect(protectedResult).toEqual({ src: 'blob:mock-asset', isObjectUrl: true });
    } finally {
      (URL as any).createObjectURL = origCreate;
    }
  });
});
