import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { AdminComponent } from './admin.component';
import { AdminUser, UserDeletionPreview, WhisperReport } from '../../core/services/admin.service';

describe('AdminComponent', () => {
  let component: AdminComponent;
  let http: HttpTestingController;

  const MOCK_USER: AdminUser = {
    id: 'user_1',
    username: 'testuser',
    email: 'test@example.com',
    name: 'Test Hero',
    created_at: '2026-08-20T12:00:00Z',
    is_admin: false,
    character_count: 2,
    dm_campaign_count: 1,
    member_campaign_count: 0,
  };

  const MOCK_PREVIEW: UserDeletionPreview = {
    user_id: 'user_1',
    username: 'testuser',
    characters_to_delete: 2,
    portraits_to_delete: 2,
    dm_campaigns_to_delete: 1,
    dm_campaign_names: ['Curse of Strahd'],
    player_characters_to_detach: 3,
    memberships_to_remove: 0,
    roll_requests_to_delete: 0,
    whispers_to_archive: 5,
    can_delete: true,
    blocking_reasons: [],
  };

  const MOCK_REPORT: WhisperReport = {
    report_id: 'rep_1',
    whisper_id: 'wh_1',
    campaign_name: 'Curse of Strahd',
    reported_by_user_id: 'user_2',
    reported_by_username: 'victim',
    reason: 'Inappropriate language',
    created_at: '2026-08-20T12:30:00Z',
    status: 'open',
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [AdminComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });

    http = TestBed.inject(HttpTestingController);
    component = TestBed.createComponent(AdminComponent).componentInstance;
  });

  afterEach(() => {
    http.verify();
  });

  it('loads users and reports on init', () => {
    component.ngOnInit();

    const usersReq = http.expectOne((r) => r.method === 'GET' && r.url.endsWith('/admin/users'));
    usersReq.flush({ users: [MOCK_USER], total: 1 });

    const reportsReq = http.expectOne((r) => r.method === 'GET' && r.url.endsWith('/admin/reports'));
    reportsReq.flush([MOCK_REPORT]);

    expect(component.users()).toEqual([MOCK_USER]);
    expect(component.totalUsers()).toBe(1);
    expect(component.reports()).toEqual([MOCK_REPORT]);
  });

  it('shows skeleton rows while users load, then the real rows', () => {
    const fixture = TestBed.createComponent(AdminComponent);
    fixture.detectChanges(); // ngOnInit -> both lists start loading
    const el: HTMLElement = fixture.nativeElement;

    expect(el.querySelectorAll('tbody forge-skeleton').length).toBeGreaterThan(0);
    expect(el.querySelector('table')!.getAttribute('aria-busy')).toBe('true');

    http.expectOne((r) => r.url.endsWith('/admin/users')).flush({ users: [MOCK_USER], total: 1 });
    http.expectOne((r) => r.url.endsWith('/admin/reports')).flush([MOCK_REPORT]);
    fixture.detectChanges();

    expect(el.querySelectorAll('tbody forge-skeleton').length).toBe(0);
    expect(el.querySelector('tbody')!.textContent).toContain('testuser');
    expect(el.querySelector('tbody')!.textContent).toContain('test@example.com');
  });

  it('filters users on search term change', () => {
    component.onSearchChange('hero');

    const searchReq = http.expectOne(
      (r) => r.method === 'GET' && r.url.includes('/admin/users') && r.params.get('search') === 'hero'
    );
    searchReq.flush({ users: [MOCK_USER], total: 1 });

    expect(component.searchQuery()).toBe('hero');
    expect(component.users().length).toBe(1);
  });

  it('handles user deletion preview and confirmation flow', () => {
    component.openDeleteModal(MOCK_USER);
    expect(component.showDeleteModal()).toBe(true);
    expect(component.selectedUser()).toEqual(MOCK_USER);

    const prevReq = http.expectOne(
      (r) => r.method === 'GET' && r.url.endsWith('/admin/users/user_1/deletion-preview')
    );
    prevReq.flush(MOCK_PREVIEW);

    expect(component.deletionPreview()).toEqual(MOCK_PREVIEW);

    // Mismatched username confirmation does not trigger delete
    component.confirmUsername.set('wrongname');
    component.confirmDelete();
    http.expectNone((r) => r.method === 'DELETE');

    // Matching username confirmation executes cascade deletion
    component.confirmUsername.set('testuser');
    component.confirmDelete();

    const delReq = http.expectOne((r) => r.method === 'DELETE' && r.url.endsWith('/admin/users/user_1'));
    delReq.flush({ ...MOCK_PREVIEW, deleted: true });

    // Expect users reload after deletion
    const reloadReq = http.expectOne((r) => r.method === 'GET' && r.url.endsWith('/admin/users'));
    reloadReq.flush({ users: [], total: 0 });

    expect(component.showDeleteModal()).toBe(false);
  });

  it('inspects whisper report context and updates status to resolved', () => {
    component.inspectReport(MOCK_REPORT);
    expect(component.showReportModal()).toBe(true);

    const detailReq = http.expectOne(
      (r) => r.method === 'GET' && r.url.endsWith('/admin/reports/rep_1')
    );
    detailReq.flush({
      ...MOCK_REPORT,
      whisper: { id: 'wh_1', message: 'Reported bad text' },
      context_whispers: [{ id: 'wh_prev', message: 'Hello' }],
    });

    expect(component.selectedReport()?.context_whispers?.length).toBe(1);

    component.resolutionNote.set('User was issued a formal warning.');
    component.updateReportStatus('resolved');

    const patchReq = http.expectOne((r) => r.method === 'PATCH' && r.url.endsWith('/admin/reports/rep_1'));
    expect(patchReq.request.body).toEqual({
      status: 'resolved',
      resolution_note: 'User was issued a formal warning.',
    });
    patchReq.flush({ ...MOCK_REPORT, status: 'resolved' });

    // Reload reports
    const reloadRep = http.expectOne((r) => r.method === 'GET' && r.url.endsWith('/admin/reports'));
    reloadRep.flush([{ ...MOCK_REPORT, status: 'resolved' }]);

    expect(component.showReportModal()).toBe(false);
  });
});
