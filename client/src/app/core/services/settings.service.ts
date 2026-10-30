import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AISettings, AISettingsUpdate } from '../models/ai-settings.model';

@Injectable({
  providedIn: 'root',
})
export class SettingsService {
  private readonly baseUrl = `${environment.apiBaseUrl}/settings`;

  constructor(private http: HttpClient) {}

  getAISettings(): Observable<AISettings> {
    return this.http.get<AISettings>(`${this.baseUrl}/ai`);
  }

  updateAISettings(update: AISettingsUpdate): Observable<AISettings> {
    return this.http.put<AISettings>(`${this.baseUrl}/ai`, update);
  }
}
