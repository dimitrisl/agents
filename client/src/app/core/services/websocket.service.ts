import { Injectable } from '@angular/core';
import { Subject } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface WsMessage {
  type: 'whisper' | 'roll_request' | 'party_update' | string;
  sender?: string;
  recipient?: string;
  message?: string;
  [key: string]: any;
}

@Injectable({
  providedIn: 'root'
})
export class WebSocketService {
  private socket: WebSocket | null = null;
  private currentCampaignId: string | null = null;

  public messages$ = new Subject<WsMessage>();

  constructor() {}

  public connect(campaignId: string): void {
    if (this.currentCampaignId === campaignId && this.socket?.readyState === WebSocket.OPEN) {
      return; // Already connected to this campaign
    }

    this.disconnect();
    this.currentCampaignId = campaignId;

    // Construct absolute WebSocket URL
    let wsUrl = environment.apiBaseUrl;

    // If apiBaseUrl is relative (e.g. /api/v1), prepend the current origin
    if (wsUrl.startsWith('/')) {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      wsUrl = `${protocol}//${window.location.host}${wsUrl}`;
    } else {
      wsUrl = wsUrl.replace('http://', 'ws://').replace('https://', 'wss://');
    }

    // Remove the /api/v1 suffix to get the root ws path
    wsUrl = wsUrl.replace('/api/v1', '');
    const fullUrl = `${wsUrl}/ws/campaigns/${encodeURIComponent(campaignId)}`;

    this.socket = new WebSocket(fullUrl);

    this.socket.onopen = () => {
      console.log(`[WebSocket] Connected to campaign channel: ${campaignId}`);
    };

    this.socket.onmessage = (event) => {
      try {
        const data: WsMessage = JSON.parse(event.data);
        this.messages$.next(data);
      } catch (e) {
        console.error('[WebSocket] Failed to parse message', event.data);
      }
    };

    this.socket.onclose = () => {
      console.log(`[WebSocket] Disconnected from campaign channel: ${campaignId}`);
    };

    this.socket.onerror = (error) => {
      console.error('[WebSocket] Error', error);
    };
  }

  public disconnect(): void {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
    this.currentCampaignId = null;
  }

  public sendMessage(msg: WsMessage): void {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(msg));
    } else {
      console.warn('[WebSocket] Cannot send message, socket is not open');
    }
  }
}
