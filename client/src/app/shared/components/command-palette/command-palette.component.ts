import {
  Component,
  ElementRef,
  HostListener,
  QueryList,
  ViewChild,
  ViewChildren,
  signal,
} from '@angular/core';
import { A11yModule } from '@angular/cdk/a11y';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ForgeBadgeComponent, ForgeCardComponent, ForgeInputDirective } from '../../ui';

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
  imports: [A11yModule, CommonModule, FormsModule, ForgeBadgeComponent, ForgeCardComponent, ForgeInputDirective],
  templateUrl: './command-palette.component.html',
  styleUrl: './command-palette.component.css',
})
export class CommandPaletteComponent {
  @ViewChild('searchInput') searchInput?: ElementRef<HTMLInputElement>;
  @ViewChildren('commandRow') commandRows?: QueryList<ElementRef<HTMLElement>>;

  isOpen = signal<boolean>(false);
  searchQuery = '';
  selectedIndex = 0;
  private previouslyFocusedElement?: HTMLElement;

  commands: CommandItem[] = [
    { icon: 'âœ¨', title: 'Open Character Forge', category: 'Navigation', route: '/forge' },
    { icon: 'ðŸ“œ', title: 'Player Dashboard Sheet', category: 'Navigation', route: '/player' },
    { icon: 'ðŸ°', title: 'Dungeon Master Workspace', category: 'Navigation', route: '/dm' },
    { icon: 'ðŸ“š', title: 'Arcane Rules Library', category: 'Navigation', route: '/rules' },
    { icon: 'âš™ï¸', title: 'System Settings', category: 'Navigation', route: '/settings' },
    { icon: 'ðŸ”‘', title: 'Quick Admin Panel', category: 'Navigation', route: '/admin' },
  ];

  filteredCommands: CommandItem[] = [...this.commands];

  constructor(private router: Router) {}

  @HostListener('window:keydown', ['$event'])
  handleKeyboardEvent(event: KeyboardEvent) {
    if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
      event.preventDefault();
      if (this.isOpen()) {
        this.close();
      } else {
        this.open();
      }
    } else if (event.key === 'Escape' && this.isOpen()) {
      this.close();
    }
  }

  handlePaletteKeydown(event: KeyboardEvent): void {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      this.moveSelection(1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      this.moveSelection(-1);
    } else if (event.key === 'Enter' && this.filteredCommands[this.selectedIndex]) {
      event.preventDefault();
      this.selectItem(this.filteredCommands[this.selectedIndex]);
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
    this.restoreFocus();
  }

  private open(): void {
    this.previouslyFocusedElement = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : undefined;
    this.isOpen.set(true);
    this.searchQuery = '';
    this.filterCommands();
    this.focusSearchInput();
  }

  private moveSelection(delta: number): void {
    if (!this.filteredCommands.length) {
      this.selectedIndex = 0;
      return;
    }

    const lastIndex = this.filteredCommands.length - 1;
    this.selectedIndex = Math.min(lastIndex, Math.max(0, this.selectedIndex + delta));
    this.scrollSelectedIntoView();
  }

  private focusSearchInput(): void {
    window.setTimeout(() => this.searchInput?.nativeElement.focus());
  }

  private restoreFocus(): void {
    window.setTimeout(() => this.previouslyFocusedElement?.focus());
  }

  private scrollSelectedIntoView(): void {
    window.setTimeout(() => {
      this.commandRows
        ?.get(this.selectedIndex)
        ?.nativeElement.scrollIntoView({ block: 'nearest' });
    });
  }
}
