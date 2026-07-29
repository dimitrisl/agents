import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';

@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="admin-container">
      <div class="phyrexian-card">
        <h2>🛡️ Machine Orthodoxy Admin Workspace</h2>
        <p class="subtitle">System diagnostics, database metrics, and user management.</p>

        <div class="stats-grid">
          <div class="stat-box">
            <span class="stat-label">Active Users</span>
            <span class="stat-value">1</span>
          </div>
          <div class="stat-box">
            <span class="stat-label">Characters Forged</span>
            <span class="stat-value">{{ totalCharacters }}</span>
          </div>
          <div class="stat-box">
            <span class="stat-label">Database Status</span>
            <span class="stat-value" style="color: #4CAF50;">ONLINE</span>
          </div>
        </div>

        <h3 style="margin-top: 1.5rem;">Registered Users</h3>
        <table class="admin-table">
          <thead>
            <tr>
              <th>Username</th>
              <th>Name</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>mitsos</strong></td>
              <td>Mitsos (DM)</td>
              <td><span class="role-badge">Superadmin</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  `,
  styles: [`
    .admin-container { max-width: 800px; margin: 0 auto; }
    .subtitle { color: var(--text-muted); margin-bottom: 1.5rem; }
    .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-bottom: 1.5rem; }
    .admin-table { width: 100%; border-collapse: collapse; margin-top: 0.5rem; }
    .admin-table th, .admin-table td { padding: 0.6rem; text-align: left; border-bottom: 1px solid var(--border-card); }
    .role-badge { background: var(--primary-red); color: #fff; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem; }
  `]
})
export class AdminComponent implements OnInit {
  totalCharacters = 0;

  constructor(private http: HttpClient) {}

  ngOnInit() {
    this.http.get<any[]>('http://localhost:8000/api/v1/characters/').subscribe((chars) => {
      this.totalCharacters = chars ? chars.length : 0;
    });
  }
}
