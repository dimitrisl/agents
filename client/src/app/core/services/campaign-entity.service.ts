import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { CampaignEntity, PasteExtractionRequest } from '../models/campaign-entity.model';
import { environment } from '../../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class CampaignEntityService {
  constructor(private http: HttpClient) {}

  getEntities(campaignName: string): Observable<CampaignEntity[]> {
    return this.http.get<CampaignEntity[]>(`${environment.apiBaseUrl}/campaigns/${encodeURIComponent(campaignName)}/entities`);
  }

  createEntity(campaignName: string, entity: CampaignEntity): Observable<CampaignEntity> {
    return this.http.post<CampaignEntity>(`${environment.apiBaseUrl}/campaigns/${encodeURIComponent(campaignName)}/entities`, entity);
  }

  updateEntity(campaignName: string, entityId: string, entity: CampaignEntity): Observable<CampaignEntity> {
    return this.http.put<CampaignEntity>(`${environment.apiBaseUrl}/campaigns/${encodeURIComponent(campaignName)}/entities/${encodeURIComponent(entityId)}`, entity);
  }

  deleteEntity(campaignName: string, entityId: string): Observable<{ success: boolean; message: string }> {
    return this.http.delete<{ success: boolean; message: string }>(`${environment.apiBaseUrl}/campaigns/${encodeURIComponent(campaignName)}/entities/${encodeURIComponent(entityId)}`);
  }

  extractEntity(campaignName: string, rawText: string): Observable<CampaignEntity> {
    const payload: PasteExtractionRequest = { raw_text: rawText };
    return this.http.post<CampaignEntity>(`${environment.apiBaseUrl}/campaigns/${encodeURIComponent(campaignName)}/entities/extract`, payload);
  }
}
