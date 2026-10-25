import { Component, computed, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  AdminService,
  AdminUser,
  UserDeletionPreview,
  WhisperReport,
} from '../../core/services/admin.service';
import { RollToastService } from '../../core/services/roll-toast.service';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeCardComponent,
  ForgeEmptyStateComponent,
  ForgeInputDirective,
  ForgeModalComponent,
  ForgePageComponent,
} from '../../shared/ui';

@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeCardComponent,
    ForgeEmptyStateComponent,
    ForgeInputDirective,
    ForgeModalComponent,
    ForgePageComponent,
  ],
  templateUrl: './admin.component.html',
  styleUrl: './admin.component.css',
})
export class AdminComponent implements OnInit {
  currentTab = signal<'users' | 'reports'>('users');
  searchQuery = signal<string>('');
  reportStatusFilter = signal<string>('all');

  users = signal<AdminUser[]>([]);
  totalUsers = signal<number>(0);
  isLoadingUsers = signal<boolean>(false);
  currentPage = signal<number>(1);
  pageSize = signal<number>(10);

  totalPages = computed(() => Math.max(1, Math.ceil(this.totalUsers() / this.pageSize())));
  showingRangeStart = computed(() =>
    this.totalUsers() === 0 ? 0 : (this.currentPage() - 1) * this.pageSize() + 1
  );
  showingRangeEnd = computed(() =>
    Math.min(this.totalUsers(), this.currentPage() * this.pageSize())
  );

  reports = signal<WhisperReport[]>([]);
  isLoadingReports = signal<boolean>(false);

  // Deletion Modal state
  showDeleteModal = signal<boolean>(false);
  selectedUser = signal<AdminUser | null>(null);
  deletionPreview = signal<UserDeletionPreview | null>(null);
  confirmUsername = signal<string>('');
  isDeleting = signal<boolean>(false);

  // Whisper Report Inspection Modal state
  showReportModal = signal<boolean>(false);
  selectedReport = signal<WhisperReport | null>(null);
  resolutionNote = signal<string>('');
  isUpdatingReport = signal<boolean>(false);

  constructor(
    private adminService: AdminService,
    private rollToast: RollToastService
  ) {}

  ngOnInit(): void {
    this.loadUsers();
    this.loadReports();
  }

  loadUsers(): void {
    this.isLoadingUsers.set(true);
    const skip = (this.currentPage() - 1) * this.pageSize();
    this.adminService.getUsers(this.searchQuery(), skip, this.pageSize()).subscribe({
      next: (resp) => {
        this.users.set(resp.users);
        this.totalUsers.set(resp.total);
        this.isLoadingUsers.set(false);
      },
      error: (err) => {
        this.isLoadingUsers.set(false);
        this.rollToast.showMessage('⚠️ ERROR', err?.error?.detail || 'Failed to load users.');
      },
    });
  }

  onSearchChange(term: string): void {
    this.searchQuery.set(term);
    this.currentPage.set(1);
    this.loadUsers();
  }

  onPageSizeChange(size: number): void {
    this.pageSize.set(Number(size) || 10);
    this.currentPage.set(1);
    this.loadUsers();
  }

  prevPage(): void {
    if (this.currentPage() > 1) {
      this.currentPage.set(this.currentPage() - 1);
      this.loadUsers();
    }
  }

  nextPage(): void {
    if (this.currentPage() < this.totalPages()) {
      this.currentPage.set(this.currentPage() + 1);
      this.loadUsers();
    }
  }

  openDeleteModal(user: AdminUser): void {
    this.selectedUser.set(user);
    this.confirmUsername.set('');
    this.deletionPreview.set(null);
    this.showDeleteModal.set(true);

    this.adminService.getDeletionPreview(user.id).subscribe({
      next: (preview) => {
        this.deletionPreview.set(preview);
      },
      error: (err) => {
        this.rollToast.showMessage('⚠️ ERROR', err?.error?.detail || 'Failed to load deletion preview.');
        this.showDeleteModal.set(false);
      },
    });
  }

  confirmDelete(): void {
    const user = this.selectedUser();
    const preview = this.deletionPreview();
    if (!user || !preview || !preview.can_delete) return;
    if (this.confirmUsername().trim() !== user.username) return;

    this.isDeleting.set(true);
    this.adminService.deleteUser(user.id).subscribe({
      next: () => {
        this.isDeleting.set(false);
        this.showDeleteModal.set(false);
        this.rollToast.showMessage('🗑️ USER DELETED', `User ${user.username} was permanently removed.`);
        this.loadUsers();
      },
      error: (err) => {
        this.isDeleting.set(false);
        this.rollToast.showMessage('⚠️ DELETE FAILED', err?.error?.detail || 'Failed to delete user.');
      },
    });
  }

  loadReports(): void {
    this.isLoadingReports.set(true);
    this.adminService.getReports(this.reportStatusFilter()).subscribe({
      next: (data) => {
        this.reports.set(data);
        this.isLoadingReports.set(false);
      },
      error: (err) => {
        this.isLoadingReports.set(false);
        this.rollToast.showMessage('⚠️ ERROR', err?.error?.detail || 'Failed to load whisper reports.');
      },
    });
  }

  onReportFilterChange(status: string): void {
    this.reportStatusFilter.set(status);
    this.loadReports();
  }

  inspectReport(report: WhisperReport): void {
    this.selectedReport.set(null);
    this.resolutionNote.set('');
    this.showReportModal.set(true);

    this.adminService.getReportDetail(report.report_id).subscribe({
      next: (detail) => {
        this.selectedReport.set(detail);
        this.resolutionNote.set(detail.resolution_note || '');
      },
      error: (err) => {
        this.rollToast.showMessage('⚠️ ERROR', err?.error?.detail || 'Failed to load report details.');
        this.showReportModal.set(false);
      },
    });
  }

  updateReportStatus(status: 'resolved' | 'dismissed'): void {
    const rep = this.selectedReport();
    if (!rep) return;

    this.isUpdatingReport.set(true);
    this.adminService.updateReport(rep.report_id, {
      status,
      resolution_note: this.resolutionNote().trim() || undefined,
    }).subscribe({
      next: () => {
        this.isUpdatingReport.set(false);
        this.showReportModal.set(false);
        this.rollToast.showMessage('✅ REPORT UPDATED', `Report marked as ${status}.`);
        this.loadReports();
      },
      error: (err) => {
        this.isUpdatingReport.set(false);
        this.rollToast.showMessage('⚠️ ERROR', err?.error?.detail || 'Failed to update report status.');
      },
    });
  }

  trackUser(_index: number, user: AdminUser): string {
    return user.id;
  }

  trackReport(_index: number, report: WhisperReport): string {
    return report.report_id;
  }
}
