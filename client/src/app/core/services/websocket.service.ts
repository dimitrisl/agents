import { Injectable, inject } from '@angular/core';
import { Subject } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AuthService } from './auth.service';

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
  private auth = inject(AuthService);

  private socket: WebSocket | null = null;
  private currentCampaignId: string | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;
  private manuallyClosed = false;

  public messages$ = new Subject<WsMessage>();

  public connect(campaignId: string): void {
    this.clearReconnectTimer();
    this.manuallyClosed = false;

    // CONNECTING counts as connected here: tearing a socket down mid-handshake
    // just to open an identical one is pure churn.
    const alive =
      this.socket?.readyState === WebSocket.OPEN ||
      this.socket?.readyState === WebSocket.CONNECTING;

    if (this.currentCampaignId === campaignId && alive) {
      return; // Already connected (or connecting) to this campaign
    }

    // The handshake is authenticated, so a tokenless attempt would just be closed
    // by the server with 1008. Bail out without claiming the campaign id, so a
    // later call (once the session is restored) still gets to connect.
    const token = this.auth.token();
    if (!token) {
      console.warn('[WebSocket] No auth token available, skipping connection');
      this.disconnect();
      return;
    }

    this.closeSocket();
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
    // The JWT rides as a query param because the browser WebSocket API offers no
    // way to set an Authorization header on the handshake.
    const fullUrl =
      `${wsUrl}/ws/campaigns/${encodeURIComponent(campaignId)}` +
      `?token=${encodeURIComponent(token)}`;

    const socket = new WebSocket(fullUrl);
    this.socket = socket;

    socket.onopen = () => {
      this.reconnectAttempts = 0;
      console.log(`[WebSocket] Connected to campaign channel: ${campaignId}`);
    };

    socket.onmessage = (event) => {
      try {
        const data: WsMessage = JSON.parse(event.data);
        this.messages$.next(data);
      } catch (e) {
        console.error('[WebSocket] Failed to parse message', event.data);
      }
    };

    socket.onclose = (event) => {
      if (this.socket === socket) {
        this.socket = null;
      }

      // 1008 is what the server sends back when the JWT is missing or expired,
      // which otherwise looks identical to a plain disconnect in the console.
      if (event.code === 1008) {
        console.warn(`[WebSocket] Rejected by server (unauthorized): ${campaignId}`);
        this.currentCampaignId = null;
        return;
      }
      console.log(`[WebSocket] Disconnected from campaign channel: ${campaignId}`);

      if (!this.manuallyClosed && this.currentCampaignId === campaignId) {
        this.scheduleReconnect(campaignId);
      }
    };

    socket.onerror = (error) => {
      console.error('[WebSocket] Error', error);
    };
  }

  public disconnect(): void {
    this.manuallyClosed = true;
    this.clearReconnectTimer();
    this.closeSocket();
    this.currentCampaignId = null;
  }

  private closeSocket(): void {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }

  private scheduleReconnect(campaignId: string): void {
    this.clearReconnectTimer();
    const delay = Math.min(1000 * 2 ** this.reconnectAttempts, 10000);
    this.reconnectAttempts += 1;
    this.reconnectTimer = setTimeout(() => {
      if (!this.manuallyClosed && this.currentCampaignId === campaignId) {
        this.connect(campaignId);
      }
    }, delay);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  public sendMessage(msg: WsMessage): void {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(msg));
    } else {
      console.warn('[WebSocket] Cannot send message, socket is not open');
    }
  }
}
