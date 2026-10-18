import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { SessionLog, SessionPrep, JourneyGraph } from '../models/session.model';
import { environment } from '../../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class SessionService {
  constructor(private http: HttpClient) {}

  getSessions(campaignName: string): Observable<SessionLog[]> {
    return this.http.get<SessionLog[]>(`${environment.apiBaseUrl}/campaigns/${encodeURIComponent(campaignName)}/sessions`);
  }

  uploadAudioSession(campaignName: string, sessionNumber: number, audioFile: File): Observable<SessionLog> {
    const formData = new FormData();
    formData.append('session_number', sessionNumber.toString());
    formData.append('audio_file', audioFile);

    return this.http.post<SessionLog>(
      `${environment.apiBaseUrl}/campaigns/${encodeURIComponent(campaignName)}/sessions/audio`,
      formData
    );
  }

  processTextSession(campaignName: string, sessionNumber: number, notes: string): Observable<SessionLog> {
    return this.http.post<SessionLog>(
      `${environment.apiBaseUrl}/campaigns/${encodeURIComponent(campaignName)}/sessions/text`,
      { session_number: sessionNumber, notes }
    );
  }

  generateSessionPrep(campaignName: string, dmIdeas: string = ''): Observable<SessionPrep> {
    return this.http.post<SessionPrep>(
      `${environment.apiBaseUrl}/campaigns/${encodeURIComponent(campaignName)}/sessions/prep`,
      { dm_ideas: dmIdeas }
    );
  }

  generateJourneyGraph(campaignName: string): Observable<JourneyGraph> {
    return this.http.post<JourneyGraph>(
      `${environment.apiBaseUrl}/campaigns/${encodeURIComponent(campaignName)}/sessions/journey`,
      {}
    );
  }
}
