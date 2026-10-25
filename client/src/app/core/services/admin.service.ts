import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface AdminUser {
  id: string;
  username: string;
  email?: string;
  name?: string;
  created_at?: string;
  is_admin: boolean;
  is_online?: boolean;
  character_count: number;
  dm_campaign_count: number;
  member_campaign_count: number;
}

export interface AdminUserListResponse {
  users: AdminUser[];
  total: number;
}

export interface UserDeletionPreview {
  user_id: string;
  username: string;
  characters_to_delete: number;
  portraits_to_delete: number;
  dm_campaigns_to_delete: number;
  dm_campaign_names: string[];
  player_characters_to_detach: number;
  memberships_to_remove: number;
  roll_requests_to_delete: number;
  whispers_to_archive: number;
  can_delete: boolean;
  blocking_reasons: string[];
}

export interface WhisperReport {
  report_id: string;
  whisper_id: string;
  campaign_name: string;
  reported_by_user_id: string;
  reported_by_username?: string;
  reason: string;
  created_at: string;
  status: 'open' | 'resolved' | 'dismissed';
  resolution_note?: string;
  resolved_at?: string;
  resolved_by_user_id?: string;
  whisper?: any;
  context_whispers?: any[];
}

@Injectable({
  providedIn: 'root',
})
export class AdminService {
  private readonly baseUrl = `${environment.apiBaseUrl}/admin`;

  constructor(private http: HttpClient) {}

  getUsers(search?: string, skip = 0, limit = 50): Observable<AdminUserListResponse> {
    let params = new HttpParams().set('skip', skip).set('limit', limit);
    if (search && search.trim()) {
      params = params.set('search', search.trim());
    }
    return this.http.get<AdminUserListResponse>(`${this.baseUrl}/users`, { params });
  }

  getDeletionPreview(userId: string): Observable<UserDeletionPreview> {
    return this.http.get<UserDeletionPreview>(`${this.baseUrl}/users/${encodeURIComponent(userId)}/deletion-preview`);
  }

  deleteUser(userId: string): Observable<any> {
    return this.http.delete(`${this.baseUrl}/users/${encodeURIComponent(userId)}`);
  }

  getReports(statusFilter?: string): Observable<WhisperReport[]> {
    let params = new HttpParams();
    if (statusFilter && statusFilter !== 'all') {
      params = params.set('status', statusFilter);
    }
    return this.http.get<WhisperReport[]>(`${this.baseUrl}/reports`, { params });
  }

  getReportDetail(reportId: string): Observable<WhisperReport> {
    return this.http.get<WhisperReport>(`${this.baseUrl}/reports/${encodeURIComponent(reportId)}`);
  }

  updateReport(reportId: string, payload: { status: string; resolution_note?: string }): Observable<any> {
    return this.http.patch(`${this.baseUrl}/reports/${encodeURIComponent(reportId)}`, payload);
  }
}
