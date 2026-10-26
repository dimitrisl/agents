import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable, shareReplay, tap } from 'rxjs';
import { campaignUrl } from '../config/api-urls';

export interface HomebrewItem {
  _id?: string;
  campaign_id?: string;
  creator_dm_id?: string;
  homebrew_type: 'weapon' | 'item' | 'spell' | 'feat' | 'feature' | 'monster';
  name: string;
  [key: string]: any;
}

@Injectable({
  providedIn: 'root'
})
export class HomebrewService {
  private http = inject(HttpClient);

  private itemsSubject = new BehaviorSubject<HomebrewItem[]>([]);
  public items$ = this.itemsSubject.asObservable();

  loadHomebrew(campaignName: string): Observable<HomebrewItem[]> {
    return this.http.get<HomebrewItem[]>(campaignUrl(campaignName, 'homebrew')).pipe(
      tap(items => this.itemsSubject.next(items))
    );
  }

  forgeWithAI(campaignName: string, prompt: string, type: string): Observable<any> {
    return this.http.post(campaignUrl(campaignName, 'homebrew/forge'), { prompt, type });
  }

  saveHomebrew(campaignName: string, item: Partial<HomebrewItem>): Observable<any> {
    return this.http.post(campaignUrl(campaignName, 'homebrew'), { type: item.homebrew_type, data: item }).pipe(
      tap(() => this.loadHomebrew(campaignName).subscribe())
    );
  }

  deleteHomebrew(campaignName: string, itemId: string): Observable<any> {
    return this.http.delete(campaignUrl(campaignName, `homebrew/${encodeURIComponent(itemId)}`)).pipe(
      tap(() => this.loadHomebrew(campaignName).subscribe())
    );
  }

  exportHomebrew(campaignName: string): Observable<any> {
    return this.http.get(campaignUrl(campaignName, 'homebrew/export'));
  }

  exportHomebrewPdf(campaignName: string): Observable<Blob> {
    const url = campaignUrl(campaignName, 'homebrew/export/pdf');
    const download$ = this.http.get(url, { responseType: 'blob' }).pipe(
      tap((blob: Blob) => {
        if (typeof window !== 'undefined' && window.URL && typeof window.URL.createObjectURL === 'function') {
          const downloadUrl = window.URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = downloadUrl;
          link.download = `${campaignName}_homebrew.pdf`;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          if (typeof window.URL.revokeObjectURL === 'function') {
            window.URL.revokeObjectURL(downloadUrl);
          }
        }
      }),
      shareReplay(1)
    );
    download$.subscribe();
    return download$;
  }

  importHomebrew(campaignName: string, items: any[]): Observable<any> {
    return this.http.post(campaignUrl(campaignName, 'homebrew/import'), { items }).pipe(
      tap(() => this.loadHomebrew(campaignName).subscribe())
    );
  }
}
