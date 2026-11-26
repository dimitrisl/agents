import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  StoryScene,
  StorySceneCastRequest,
  StorySceneCreatePayload,
  StorySceneDismissRequest,
  StorySceneUpdatePayload,
} from '../models/story-scene.model';

@Injectable({
  providedIn: 'root',
})
export class StorySceneService {
  constructor(private http: HttpClient) {}

  private baseUrl(campaignName: string): string {
    return `${environment.apiBaseUrl}/campaigns/${encodeURIComponent(campaignName)}/story-scenes`;
  }

  listScenes(campaignName: string): Observable<StoryScene[]> {
    return this.http.get<StoryScene[]>(this.baseUrl(campaignName));
  }

  createScene(campaignName: string, payload: StorySceneCreatePayload): Observable<StoryScene> {
    return this.http.post<StoryScene>(this.baseUrl(campaignName), payload);
  }

  updateScene(
    campaignName: string,
    sceneId: string,
    payload: StorySceneUpdatePayload
  ): Observable<StoryScene> {
    return this.http.put<StoryScene>(
      `${this.baseUrl(campaignName)}/${encodeURIComponent(sceneId)}`,
      payload
    );
  }

  deleteScene(
    campaignName: string,
    sceneId: string
  ): Observable<{ success: boolean; message: string }> {
    return this.http.delete<{ success: boolean; message: string }>(
      `${this.baseUrl(campaignName)}/${encodeURIComponent(sceneId)}`
    );
  }

  castCard(
    campaignName: string,
    sceneId: string,
    body: StorySceneCastRequest
  ): Observable<{ success: boolean; message: string }> {
    return this.http.post<{ success: boolean; message: string }>(
      `${this.baseUrl(campaignName)}/${encodeURIComponent(sceneId)}/cast`,
      body
    );
  }

  dismissPopup(
    campaignName: string,
    body: StorySceneDismissRequest = { target_mode: 'all', target_char_ids: [] }
  ): Observable<{ success: boolean; message: string }> {
    return this.http.post<{ success: boolean; message: string }>(
      `${this.baseUrl(campaignName)}/dismiss`,
      body
    );
  }
}
