import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';
import { BehaviorSubject, Observable, tap } from 'rxjs';

export interface HomebrewItem {
  _id?: string;
  campaign_id?: string;
  creator_dm_id?: string;
  homebrew_type: 'weapon' | 'item' | 'spell' | 'feat' | 'feature';
  name: string;
  [key: string]: any;
}

@Injectable({
  providedIn: 'root'
})
export class HomebrewService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiBaseUrl}/campaigns`;

  private itemsSubject = new BehaviorSubject<HomebrewItem[]>([]);
  public items$ = this.itemsSubject.asObservable();

  loadHomebrew(campaignName: string): Observable<HomebrewItem[]> {
    return this.http.get<HomebrewItem[]>(`${this.apiUrl}/${campaignName}/homebrew`).pipe(
      tap(items => this.itemsSubject.next(items))
    );
  }

  forgeWithAI(campaignName: string, prompt: string, type: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/${campaignName}/homebrew/forge`, { prompt, type });
  }

  saveHomebrew(campaignName: string, item: Partial<HomebrewItem>): Observable<any> {
    return this.http.post(`${this.apiUrl}/${campaignName}/homebrew`, { type: item.homebrew_type, data: item }).pipe(
      tap(() => this.loadHomebrew(campaignName).subscribe())
    );
  }

  deleteHomebrew(campaignName: string, itemId: string): Observable<any> {
    return this.http.delete(`${this.apiUrl}/${campaignName}/homebrew/${itemId}`).pipe(
      tap(() => this.loadHomebrew(campaignName).subscribe())
    );
  }

  exportHomebrew(campaignName: string): Observable<any> {
    return this.http.get(`${this.apiUrl}/${campaignName}/homebrew/export`);
  }

  importHomebrew(campaignName: string, items: any[]): Observable<any> {
    return this.http.post(`${this.apiUrl}/${campaignName}/homebrew/import`, { items }).pipe(
      tap(() => this.loadHomebrew(campaignName).subscribe())
    );
  }
}
