import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { map } from 'rxjs/operators';
import { environment } from '../../../environments/environment';

export type CampaignAssetKind = 'map' | 'token' | 'scene';

export interface ResolvedDisplayImage {
  src: string;
  isObjectUrl: boolean;
}

@Injectable({
  providedIn: 'root',
})
export class AssetService {
  constructor(private http: HttpClient) {}

  uploadAsset(
    campaignName: string,
    file: File,
    kind: CampaignAssetKind = 'map'
  ): Observable<{ url: string; filename?: string; kind?: string }> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('kind', kind);
    return this.http.post<{ url: string; filename?: string; kind?: string }>(
      `${environment.apiBaseUrl}/campaigns/${encodeURIComponent(campaignName)}/assets`,
      formData
    );
  }

  isProtectedCampaignAssetUrl(url: string): boolean {
    const clean = (url || '').trim();
    if (!clean) return false;
    if (/^\/api\/v1\/campaigns\/[^/]+\/assets\//.test(clean)) {
      return true;
    }
    const apiBase = environment.apiBaseUrl.replace(/\/+$/, '');
    if (clean.startsWith(`${apiBase}/campaigns/`)) {
      const rest = clean.slice(`${apiBase}/campaigns/`.length);
      return /^[^/]+\/assets\//.test(rest);
    }
    return false;
  }

  resolveAssetRequestUrl(url: string): string {
    if (url.startsWith('/api/v1/') && environment.apiBaseUrl !== '/api/v1') {
      return `${environment.apiBaseUrl}${url.slice('/api/v1'.length)}`;
    }
    return url;
  }

  resolveDisplayImage(rawUrl: string | null | undefined): Observable<ResolvedDisplayImage> {
    const clean = (rawUrl || '').trim();
    if (!clean) {
      return of({ src: '', isObjectUrl: false });
    }
    if (!this.isProtectedCampaignAssetUrl(clean)) {
      return of({ src: clean, isObjectUrl: false });
    }
    const requestUrl = this.resolveAssetRequestUrl(clean);
    return this.http.get(requestUrl, { responseType: 'blob' }).pipe(
      map((blob) => {
        if (typeof URL === 'undefined' || typeof URL.createObjectURL !== 'function') {
          return { src: clean, isObjectUrl: false };
        }
        return { src: URL.createObjectURL(blob), isObjectUrl: true };
      })
    );
  }
}
