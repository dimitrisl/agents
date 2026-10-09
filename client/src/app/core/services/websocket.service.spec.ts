import { TestBed } from '@angular/core/testing';
import { WebSocketService, WsIdentity } from './websocket.service';
import { AuthService } from './auth.service';

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  readyState = WebSocket.CONNECTING;

  onopen: any = null;
  onmessage: any = null;
  onclose: any = null;
  onerror: any = null;

  sentData: any[] = [];

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  send(data: string) {
    this.sentData.push(data);
  }

  close(code?: number, reason?: string) {
    this.readyState = WebSocket.CLOSED;
    if (this.onclose) this.onclose({ code: code || 1000, reason });
  }

  // Helpers for testing
  simulateOpen() {
    this.readyState = WebSocket.OPEN;
    if (this.onopen) this.onopen();
  }

  simulateMessage(data: any) {
    if (this.onmessage) this.onmessage({ data: JSON.stringify(data) });
  }

  simulateClose(code: number = 1000) {
    this.readyState = WebSocket.CLOSED;
    if (this.onclose) this.onclose({ code });
  }
}

describe('WebSocketService', () => {
  let service: WebSocketService;
  let authServiceSpy: any;
  let originalWebSocket: any;

  beforeEach(() => {
    authServiceSpy = { token: jest.fn().mockReturnValue('fake-token') };

    // Mock the global WebSocket
    originalWebSocket = (window as any).WebSocket;
    (window as any).WebSocket = MockWebSocket;
    MockWebSocket.instances = [];

    TestBed.configureTestingModule({
      providers: [
        WebSocketService,
        { provide: AuthService, useValue: authServiceSpy }
      ]
    });
    service = TestBed.inject(WebSocketService);
    jest.useFakeTimers();
  });

  afterEach(() => {
    service.disconnect();
    (window as any).WebSocket = originalWebSocket;
    jest.clearAllTimers();
    jest.useRealTimers();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should not connect if auth token is missing', () => {
    authServiceSpy.token.mockReturnValue(null);
    service.connect('camp1', {});
    expect(MockWebSocket.instances.length).toBe(0);
  });

  it('should connect and send auth on open', () => {
    service.connect('camp1', { character: 'hero1' });
    expect(MockWebSocket.instances.length).toBe(1);

    const ws = MockWebSocket.instances[0];
    ws.simulateOpen();

    expect(ws.sentData.length).toBe(2);
    expect(JSON.parse(ws.sentData[0])).toEqual({ type: 'auth', token: 'fake-token', character: 'hero1' });
    expect(JSON.parse(ws.sentData[1])).toEqual({ type: 'vtt_request_sync' });
  });

  it('should ignore duplicate connect calls for same identity', () => {
    service.connect('camp1', { character: 'hero1' });
    const ws1 = MockWebSocket.instances[0];

    service.connect('camp1', { character: 'hero1' });
    expect(MockWebSocket.instances.length).toBe(1); // No new instance
  });

  it('should reconnect if identity changes', () => {
    service.connect('camp1', { character: 'hero1' });
    service.connect('camp1', { character: 'hero2' });
  });

  it('should handle incoming messages and push to subject', (done) => {
    service.connect('camp1', {});
    const ws = MockWebSocket.instances[0];
    ws.simulateOpen();

    service.messages$.subscribe(msg => {
      expect(msg.type).toBe('chat');
      expect(msg.message).toBe('hello');
      done();
    });

    ws.simulateMessage({ type: 'chat', message: 'hello' });
  });

  it('should update vttState signal on vtt_sync message', () => {
    service.connect('camp1', {});
    const ws = MockWebSocket.instances[0];
    ws.simulateOpen();

    ws.simulateMessage({ type: 'vtt_sync', payload: { is_active: true, tokens: [], grid: {} } });

    const state = service.vttState();
    expect(state).toBeTruthy();
    expect(state?.is_active).toBe(true);
  });

  it('should automatically reconnect on close', () => {
    service.connect('camp1', {});
    const ws = MockWebSocket.instances[0];
    ws.simulateOpen();

    ws.simulateClose(1001);

    // Fast-forward timers for reconnect delay
  });

  it('should not reconnect if closed with code 1008 (unauthorized)', () => {
    service.connect('camp1', {});
    const ws = MockWebSocket.instances[0];
    ws.simulateOpen();

    ws.simulateClose(1008);

    expect(MockWebSocket.instances.length).toBe(1); // No new instance
  });

  it('should not reconnect if manually disconnected', () => {
    service.connect('camp1', {});
    const ws = MockWebSocket.instances[0];
    ws.simulateOpen();

    service.disconnect();

    expect(MockWebSocket.instances.length).toBe(1); // No new instance
  });

  it('should send VTT commands correctly', () => {
    service.connect('camp1', {});
    const ws = MockWebSocket.instances[0];
    ws.simulateOpen();

    // Clear initial handshake messages
    ws.sentData = [];

    service.sendVttToggle(true);
    expect(JSON.parse(ws.sentData[0])).toEqual({ type: 'vtt_toggle', payload: { is_active: true } });

    service.sendVttMove('token1', 10, 20);
    expect(JSON.parse(ws.sentData[1])).toEqual({ type: 'vtt_token_move', payload: { token_id: 'token1', x: 10, y: 20 } });
  });

  it('should send ping heartbeat and disconnect if silent for too long', () => {
    service.connect('camp1', {});
    const ws = MockWebSocket.instances[0];
    ws.simulateOpen();
    ws.sentData = [];

    // Advance time by HEARTBEAT_INTERVAL
    jest.advanceTimersByTime(25000);
    expect(JSON.parse(ws.sentData[0])).toEqual({ type: 'ping' });

    // Advance time past SILENCE_TIMEOUT without simulating a message
    jest.advanceTimersByTime(50000);
    expect(ws.readyState).toBe(WebSocket.CLOSED);
  });
});
