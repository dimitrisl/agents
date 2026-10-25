import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { VttGridComponent } from './vtt-grid.component';
import { WebSocketService } from '../../../core/services/websocket.service';
import { VTTScene, VTTSceneHistory } from '../../../core/models/vtt.model';
import { environment } from '../../../../environments/environment';

describe('VttGridComponent', () => {
  let component: VttGridComponent;
  let http: HttpTestingController;
  let wsService: WebSocketService;

  const MOCK_SCENE: VTTScene = {
    scene_id: 'sc_1',
    campaign_name: 'TestCampaign',
    name: 'Dungeon Level 1',
    dm_notes: 'Secret door behind altar',
    grid: { width: 30, height: 30, cell_size: 50 },
    tokens: [],
    fog: { enabled: true, revealed: [0, 1, 2] },
    order: 0,
    is_active_scene: true,
  };

  const MOCK_HISTORY: VTTSceneHistory = {
    campaign_name: 'TestCampaign',
    scene_id: 'sc_1',
    scene_name: 'Dungeon Level 1',
    activated_at: '2026-10-24T12:00:00Z',
    activated_by_user_id: 'dm_user_1',
  };

  let mockCtx: any;

  beforeEach(() => {
    mockCtx = {
      clearRect: jest.fn(),
      fillRect: jest.fn(),
      strokeRect: jest.fn(),
      save: jest.fn(),
      restore: jest.fn(),
      setLineDash: jest.fn(),
    };
    jest.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(mockCtx);

    TestBed.configureTestingModule({
      imports: [VttGridComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        WebSocketService,
      ],
    });

    http = TestBed.inject(HttpTestingController);
    wsService = TestBed.inject(WebSocketService);
    const fixture = TestBed.createComponent(VttGridComponent);
    component = fixture.componentInstance;
    component.campaignName = 'TestCampaign';
    component.role = 'dm';
  });

  afterEach(() => {
    http.verify();
    jest.restoreAllMocks();
  });

  it('initializes with default scene modal tab as scenes', () => {
    expect(component.sceneModalTab).toBe('scenes');
  });

  it('switches to history tab and loads scene history', () => {
    component.setSceneModalTab('history');
    expect(component.sceneModalTab).toBe('history');

    const req = http.expectOne(`${environment.apiBaseUrl}/campaigns/TestCampaign/scenes/history`);
    expect(req.request.method).toBe('GET');
    req.flush([MOCK_HISTORY]);

    expect(component.sceneHistory.length).toBe(1);
    expect(component.sceneHistory[0].scene_name).toBe('Dungeon Level 1');
  });

  it('toggles scene notes editor and saves scene notes', () => {
    component.toggleSceneNotes(MOCK_SCENE);
    expect(component.expandedSceneNotesId).toBe('sc_1');

    MOCK_SCENE.dm_notes = 'Updated trap location';
    component.saveSceneNotes(MOCK_SCENE);

    const putReq = http.expectOne(`${environment.apiBaseUrl}/campaigns/TestCampaign/scenes/sc_1`);
    expect(putReq.request.method).toBe('PUT');
    expect(putReq.request.body).toEqual({
      name: 'Dungeon Level 1',
      dm_notes: 'Updated trap location',
    });
    putReq.flush({ ...MOCK_SCENE, dm_notes: 'Updated trap location' });

    // Expect scenes list to be reloaded after save
    const getReq = http.expectOne(`${environment.apiBaseUrl}/campaigns/TestCampaign/scenes`);
    getReq.flush([MOCK_SCENE]);

    expect(component.expandedSceneNotesId).toBeNull();
  });

  it('supports rectangle fog selection modes and sends rect payload', () => {
    jest.spyOn(wsService, 'sendVttFogReveal').mockImplementation();
    jest.spyOn(wsService, 'sendVttFogHide').mockImplementation();

    component.setFogBrush('rect_reveal');
    expect(component.fogBrushMode).toBe('rect_reveal');

    // Simulate mouse drag rectangle: from (2, 3) to (5, 7)
    component.rectStartCol = 2;
    component.rectStartRow = 3;
    component.rectCurrentCol = 5;
    component.rectCurrentRow = 7;
    (component as any).isPaintingFog = true;

    component.onFogMouseUp();

    expect(wsService.sendVttFogReveal).toHaveBeenCalledWith(undefined, {
      x: 2,
      y: 3,
      w: 4,
      h: 5,
    });
    expect(component.rectStartCol).toBeNull();

    // Box hide mode
    component.setFogBrush('rect_hide');
    component.rectStartCol = 4;
    component.rectStartRow = 4;
    component.rectCurrentCol = 1;
    component.rectCurrentRow = 2;
    (component as any).isPaintingFog = true;

    component.onFogMouseUp();

    expect(wsService.sendVttFogHide).toHaveBeenCalledWith(undefined, {
      x: 1,
      y: 2,
      w: 4,
      h: 3,
    });
  });

  it('optimistically updates vttState on mouseup for brush reveal and hide', () => {
    jest.spyOn(wsService, 'sendVttFogReveal').mockImplementation();
    jest.spyOn(wsService, 'sendVttFogHide').mockImplementation();

    // Initial state: 10x10 grid with fog enabled and cell 0 revealed
    wsService.vttState.set({
      is_active: true,
      grid: { width: 10, height: 10, cell_size: 50 },
      tokens: [],
      fog: { enabled: true, revealed: [0] },
    });

    // 1. Paint reveal cell (1, 2) -> index 21
    component.fogBrushMode = 'reveal';
    (component as any).isPaintingFog = true;
    (component as any).paintedFogCells.add('1,2');

    component.onFogMouseUp();

    expect(wsService.vttState()?.fog?.revealed).toContain(21);
    expect(wsService.vttState()?.fog?.revealed).toContain(0);
    expect(wsService.sendVttFogReveal).toHaveBeenCalledWith([[1, 2]]);

    // 2. Paint hide cell (0, 0) -> index 0
    component.fogBrushMode = 'hide';
    (component as any).isPaintingFog = true;
    (component as any).paintedFogCells.add('0,0');

    component.onFogMouseUp();

    expect(wsService.vttState()?.fog?.revealed).not.toContain(0);
    expect(wsService.vttState()?.fog?.revealed).toContain(21);
    expect(wsService.sendVttFogHide).toHaveBeenCalledWith([[0, 0]]);
  });

  it('caches canvas.getBoundingClientRect on mousedown and clears on mouseup', () => {
    const mockCanvas = document.createElement('canvas');
    const mockRect = { left: 10, top: 20, width: 500, height: 500 } as DOMRect;
    jest.spyOn(mockCanvas, 'getBoundingClientRect').mockReturnValue(mockRect);
    component.fogCanvasRef = { nativeElement: mockCanvas };

    component.fogBrushMode = 'reveal';
    const fakeEvent = new MouseEvent('mousedown', { clientX: 60, clientY: 70 });
    jest.spyOn(fakeEvent, 'preventDefault');

    component.onFogMouseDown(fakeEvent);

    expect((component as any).cachedCanvasRect).toEqual(mockRect);
    expect((component as any).isPaintingFog).toBe(true);

    component.onFogMouseUp();
    expect((component as any).cachedCanvasRect).toBeNull();
    expect((component as any).isPaintingFog).toBe(false);
  });

  it('renders punch-out fog canvas filling once and punching out holes with clearRect', () => {
    const mockCanvas = document.createElement('canvas');
    component.fogCanvasRef = { nativeElement: mockCanvas };

    wsService.vttState.set({
      is_active: true,
      grid: { width: 10, height: 10, cell_size: 50 },
      tokens: [],
      fog: { enabled: true, revealed: [5, 12] },
    });

    component.renderFogCanvas();

    // 1. Initial clear of whole canvas (500x500)
    expect(mockCtx.clearRect).toHaveBeenCalledWith(0, 0, 500, 500);
    // 2. Full canvas fill with DM fog color
    expect(mockCtx.fillRect).toHaveBeenCalledWith(0, 0, 500, 500);
    // 3. Holes punched out with clearRect for revealed cells:
    // Cell 5 -> x=5, y=0 -> px=(250, 0)
    expect(mockCtx.clearRect).toHaveBeenCalledWith(250, 0, 50, 50);
    // Cell 12 -> x=2, y=1 -> px=(100, 50)
    expect(mockCtx.clearRect).toHaveBeenCalledWith(100, 50, 50, 50);
    // Redundant strokeRect should NOT be called for individual cells
    expect(mockCtx.strokeRect).not.toHaveBeenCalled();
  });

  it('guards effect against redrawing fog canvas when tokens move or HP changes', () => {
    const renderSpy = jest.spyOn(component, 'renderFogCanvas');

    // Initial state
    wsService.vttState.set({
      is_active: true,
      grid: { width: 10, height: 10, cell_size: 50 },
      tokens: [{ id: 't1', name: 'Fighter', x: 0, y: 0, hp: 10, max_hp: 10, size: 1, is_enemy: false, is_hidden: false }],
      fog: { enabled: true, revealed: [5, 12] },
    });
    TestBed.flushEffects();
    renderSpy.mockClear();

    // Token moves - new object and new array instances with identical values
    wsService.vttState.set({
      is_active: true,
      grid: { width: 10, height: 10, cell_size: 50 },
      tokens: [{ id: 't1', name: 'Fighter', x: 50, y: 50, hp: 8, max_hp: 10, size: 1, is_enemy: false, is_hidden: false }],
      fog: { enabled: true, revealed: [5, 12] },
    });
    TestBed.flushEffects();

    expect(renderSpy).not.toHaveBeenCalled();
  });

  it('avoids redundant canvas redraws when mouse moves within the same grid cell during brush drag', () => {
    const mockCanvas = document.createElement('canvas');
    component.fogCanvasRef = { nativeElement: mockCanvas };
    const mockRect = { left: 0, top: 0, width: 500, height: 500 } as DOMRect;
    jest.spyOn(mockCanvas, 'getBoundingClientRect').mockReturnValue(mockRect);

    wsService.vttState.set({
      is_active: true,
      grid: { width: 10, height: 10, cell_size: 50 },
      tokens: [],
      fog: { enabled: true, revealed: [] },
    });

    component.fogBrushMode = 'reveal';
    component.onFogMouseDown(new MouseEvent('mousedown', { clientX: 25, clientY: 25 }));
    const renderSpy = jest.spyOn(component, 'renderFogCanvas');

    // Move slightly within cell (0, 0): clientX=30, clientY=30 -> same cell (0, 0)
    component.onFogMouseMove(new MouseEvent('mousemove', { clientX: 30, clientY: 30 }));
    expect(renderSpy).not.toHaveBeenCalled();

    // Move to adjacent cell (1, 0): clientX=75, clientY=25 -> new cell (1, 0)
    component.onFogMouseMove(new MouseEvent('mousemove', { clientX: 75, clientY: 25 }));
    expect(renderSpy).toHaveBeenCalledTimes(1);
  });
});
