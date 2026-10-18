import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { CampaignSkeleton } from '../models/campaign-skeleton.model';
import { environment } from '../../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class CampaignPlotService {
  constructor(private http: HttpClient) {}

  getSkeleton(campaignName: string): Observable<CampaignSkeleton> {
    return this.http.get<CampaignSkeleton>(`${environment.apiBaseUrl}/campaigns/${encodeURIComponent(campaignName)}/skeleton`);
  }

  updateSkeleton(campaignName: string, skeleton: CampaignSkeleton): Observable<CampaignSkeleton> {
    return this.http.post<CampaignSkeleton>(`${environment.apiBaseUrl}/campaigns/${encodeURIComponent(campaignName)}/skeleton`, skeleton);
  }

  generateOutlines(campaignName: string): Observable<CampaignSkeleton> {
    return this.http.post<CampaignSkeleton>(`${environment.apiBaseUrl}/campaigns/${encodeURIComponent(campaignName)}/skeleton/generate-outlines`, {});
  }
}
