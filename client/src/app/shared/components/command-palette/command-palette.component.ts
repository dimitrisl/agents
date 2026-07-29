import { Component, HostListener, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

export interface CommandItem {
  icon: string;
  title: string;
  category: 'Navigation' | 'Action' | 'Rules';
  route?: string;
  action?: () => void;
}

@Component({
  selector: 'app-command-palette',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div *ngIf="isOpen()" class="palette-backdrop" (click)="close()">
      <div class="palette-card phyrexian-card animated-fade" (click)="$event.stopPropagation()">
        <div class="palette-input-row">
          <span class="search-icon">🔍</span>
          <input
            type="text"
            class="palette-input"
            placeholder="Type a command or search... (e.g. Forge, Rules, Rest)"
            [(ngModel)]="searchQuery"
            (input)="filterCommands()"
            #searchInput
          />
          <span class="esc-badge">ESC</span>
        </div>

        <div class="palette-results">
          <div
            *ngFor="let item of filteredCommands; let i = index"
            class="command-row"
            [class.selected]="i === selectedIndex"
            (click)="selectItem(item)">
            <div class="cmd-title-row">
              <span class="cmd-icon">{{ item.icon }}</span>
              <strong class="cmd-title">{{ item.title }}</strong>
            </div>
            <span class="category-badge">{{ item.category }}</span>
          </div>

          <div *ngIf="filteredCommands.length === 0" class="no-results">
            No matching commands found.
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .palette-backdrop {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0, 0, 0, 0.75);
      backdrop-filter: blur(8px);
      display: flex;
      justify-content: center;
      align-items: flex-start;
      padding-top: 10vh;
      z-index: 10000;
    }
    .palette-card {
      width: 100%;
      max-width: 600px;
      padding: 1rem;
      border: 1px solid var(--theme-accent);
      box-shadow: 0 15px 50px rgba(0, 0, 0, 0.8), 0 0 25px rgba(255, 75, 75, 0.3);
    }
    .palette-input-row {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      background: rgba(0,0,0,0.4);
      border-radius: 8px;
      padding: 0.5rem 0.8rem;
      border: 1px solid var(--border-card);
    }
    .search-icon { font-size: 1.1rem; }
    .palette-input {
      background: none;
      border: none;
      outline: none;
      color: #fff;
      font-size: 1.1rem;
      font-family: var(--font-body);
      width: 100%;
    }
    .esc-badge {
      font-size: 0.7rem;
      background: rgba(255,255,255,0.1);
      padding: 0.2rem 0.5rem;
      border-radius: 4px;
      color: var(--text-muted);
    }
    .palette-results {
      margin-top: 0.75rem;
      max-height: 350px;
      overflow-y: auto;
    }
    .command-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0.65rem 0.85rem;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.2s;
    }
    .command-row:hover, .command-row.selected {
      background: rgba(255, 75, 75, 0.2);
      border-left: 3px solid var(--theme-accent);
    }
    .cmd-title-row { display: flex; align-items: center; gap: 0.6rem; }
    .cmd-icon { font-size: 1.1rem; }
    .cmd-title { font-size: 0.95rem; }
    .category-badge {
      font-size: 0.72rem;
      color: var(--text-gold);
      background: rgba(212, 175, 55, 0.15);
      padding: 0.15rem 0.45rem;
      border-radius: 4px;
    }
    .no-results {
      padding: 1.5rem;
      text-align: center;
      color: var(--text-muted);
    }
  `]
})
export class CommandPaletteComponent {
  isOpen = signal<boolean>(false);
  searchQuery = '';
  selectedIndex = 0;

  commands: CommandItem[] = [
    { icon: '✨', title: 'Open Character Forge', category: 'Navigation', route: '/forge' },
    { icon: '📜', title: 'Player Dashboard Sheet', category: 'Navigation', route: '/player' },
    { icon: '🏰', title: 'Dungeon Master Workspace', category: 'Navigation', route: '/dm' },
    { icon: '📚', title: 'Arcane Rules Library', category: 'Navigation', route: '/rules' },
    { icon: '⚙️', title: 'System Settings', category: 'Navigation', route: '/settings' },
    { icon: '🔑', title: 'Quick Admin Panel', category: 'Navigation', route: '/admin' },
  ];

  filteredCommands: CommandItem[] = [...this.commands];

  constructor(private router: Router) {}

  @HostListener('window:keydown', ['$event'])
  handleKeyboardEvent(event: KeyboardEvent) {
    if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
      event.preventDefault();
      this.isOpen.set(!this.isOpen());
      if (this.isOpen()) {
        this.searchQuery = '';
        this.filterCommands();
      }
    } else if (event.key === 'Escape' && this.isOpen()) {
      this.close();
    }
  }

  filterCommands() {
    const query = this.searchQuery.toLowerCase().trim();
    if (!query) {
      this.filteredCommands = [...this.commands];
    } else {
      this.filteredCommands = this.commands.filter(
        (c) => c.title.toLowerCase().includes(query) || c.category.toLowerCase().includes(query)
      );
    }
    this.selectedIndex = 0;
  }

  selectItem(item: CommandItem) {
    this.close();
    if (item.route) {
      this.router.navigate([item.route]);
    } else if (item.action) {
      item.action();
    }
  }

  close() {
    this.isOpen.set(false);
  }
}
