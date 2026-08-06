import { Injectable, inject } from '@angular/core';
import { Subject } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AuthService } from './auth.service';

export interface WsMessage {
  type: 'whisper' | 'roll_request' | 'roll_result' | 'party_update' | string;
  sender?: string;
  recipient?: string;
  message?: string;
  [key: string]: any;
}

/**
 * Who is behind this socket. The server routes private traffic with it, so a
 * whisper for one hero never reaches the rest of the table.
 */
export interface WsIdentity {
  role: 'dm' | 'player';
  character?: string;
}

/** How often the client pings to keep the tunnel from idling the socket out. */
const HEARTBEAT_INTERVAL = 25000;
/** No frame at all for this long means the connection is dead, `close` or not. */
const SILENCE_TIMEOUT = 70000;

@Injectable({
  providedIn: 'root'
})
export class WebSocketService {
  private auth = inject(AuthService);

  private socket: WebSocket | null = null;
  private currentCampaignId: string | null = null;
  private currentIdentity: WsIdentity | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;
  private manuallyClosed = false;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private lastMessageAt = 0;

  public messages$ = new Subject<WsMessage>();

  /**
   * Fires every time the channel comes up — first connect and every reconnect.
   * Subscribers use it to re-sync whatever they missed while it was down.
   */
  public opened$ = new Subject<string>();

  public connect(campaignId: string, identity: WsIdentity): void {
    this.clearReconnectTimer();
    this.manuallyClosed = false;

    // CONNECTING counts as connected here: tearing a socket down mid-handshake
    // just to open an identical one is pure churn.
    const alive =
      this.socket?.readyState === WebSocket.OPEN ||
      this.socket?.readyState === WebSocket.CONNECTING;

    // A changed identity (the player swapped hero) has to be re-announced, so
    // that only counts as "already connected" when it matches too.
    if (this.currentCampaignId === campaignId && this.isSameIdentity(identity) && alive) {
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
    this.currentIdentity = identity;

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
    const character = identity.character
      ? `&character=${encodeURIComponent(identity.character)}`
      : '';
    const fullUrl =
      `${wsUrl}/ws/campaigns/${encodeURIComponent(campaignId)}` +
      `?token=${encodeURIComponent(token)}` +
      `&role=${encodeURIComponent(identity.role)}${character}`;

    const socket = new WebSocket(fullUrl);
    this.socket = socket;

    socket.onopen = () => {
      this.reconnectAttempts = 0;
      console.log(`[WebSocket] Connected to campaign channel: ${campaignId}`);
      this.startHeartbeat(socket);
      // Anything that happened while the socket was down was missed entirely, so
      // subscribers get a chance to re-read the history instead of showing a gap
      // until someone hits refresh.
      this.opened$.next(campaignId);
    };

    socket.onmessage = (event) => {
      this.lastMessageAt = Date.now();
      try {
        const data: WsMessage = JSON.parse(event.data);
        if (data.type === 'pong') return; // Heartbeat only, nothing to show.
        this.messages$.next(data);
      } catch (e) {
        console.error('[WebSocket] Failed to parse message', event.data);
      }
    };

    socket.onclose = (event) => {
      // A socket that has already been replaced (campaign switch, hero swap) must
      // not resurrect itself and fight the connection that superseded it.
      const isCurrent = this.socket === socket;
      if (isCurrent) {
        this.socket = null;
      }

      // 1008 is what the server sends back when the JWT is missing or expired,
      // which otherwise looks identical to a plain disconnect in the console.
      if (event.code === 1008) {
        console.warn(`[WebSocket] Rejected by server (unauthorized): ${campaignId}`);
        if (isCurrent) {
          this.currentCampaignId = null;
          this.currentIdentity = null;
        }
        return;
      }
      console.log(`[WebSocket] Disconnected from campaign channel: ${campaignId}`);

      if (isCurrent && !this.manuallyClosed && this.currentCampaignId === campaignId) {
        this.scheduleReconnect(campaignId, identity);
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
    this.currentIdentity = null;
  }

  private isSameIdentity(identity: WsIdentity): boolean {
    return (
      this.currentIdentity?.role === identity.role &&
      (this.currentIdentity?.character || '') === (identity.character || '')
    );
  }

  private closeSocket(): void {
    this.stopHeartbeat();
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }

  /**
   * A socket can die without ever firing `close` — a proxy or tunnel drops it and
   * the browser keeps believing it is OPEN, so messages simply stop arriving and
   * the page looks frozen until someone reloads. The ping keeps the tunnel warm,
   * and the silence watchdog tears down a connection that has gone quiet so the
   * normal reconnect path can take over.
   */
  private startHeartbeat(socket: WebSocket): void {
    this.stopHeartbeat();
    this.lastMessageAt = Date.now();

    this.heartbeatTimer = setInterval(() => {
      if (this.socket !== socket || socket.readyState !== WebSocket.OPEN) {
        this.stopHeartbeat();
        return;
      }

      if (Date.now() - this.lastMessageAt > SILENCE_TIMEOUT) {
        console.warn('[WebSocket] Channel went silent, reconnecting');
        this.stopHeartbeat();
        socket.close();
        return;
      }

      socket.send(JSON.stringify({ type: 'ping' }));
    }, HEARTBEAT_INTERVAL);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer !== null) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private scheduleReconnect(campaignId: string, identity: WsIdentity): void {
    this.clearReconnectTimer();
    const delay = Math.min(1000 * 2 ** this.reconnectAttempts, 10000);
    this.reconnectAttempts += 1;
    this.reconnectTimer = setTimeout(() => {
      if (!this.manuallyClosed && this.currentCampaignId === campaignId) {
        this.connect(campaignId, identity);
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
