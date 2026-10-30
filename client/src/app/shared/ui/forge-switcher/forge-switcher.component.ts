import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  ElementRef,
  EventEmitter,
  Input,
  Output,
  ViewChild,
} from '@angular/core';
import { CdkConnectedOverlay, CdkOverlayOrigin, ConnectedPosition } from '@angular/cdk/overlay';
import { CdkListbox, CdkOption, ListboxValueChangeEvent } from '@angular/cdk/listbox';
import { ForgeIconComponent } from '../forge-icon/forge-icon.component';

export interface ForgeSwitcherOption {
  id: string;
  title: string;
  subtitle?: string;
  /** Avatar image; when absent the option shows `badge` or the title's initial. */
  imageUrl?: string | null;
  /** Shown instead of the initial when there is no image, e.g. "🏰". */
  badge?: string;
}

/**
 * "Which one is active?" picker for page headers (hero, campaign): a button as
 * tall as the header actions that opens a styled, keyboard-navigable list.
 * Replaces a native <select>, whose popup can't be styled and renders OS-blue.
 */
@Component({
  selector: 'forge-switcher',
  standalone: true,
  imports: [CdkOverlayOrigin, CdkConnectedOverlay, CdkListbox, CdkOption, ForgeIconComponent],
  templateUrl: './forge-switcher.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'block min-w-0' },
})
export class ForgeSwitcherComponent {
  @Input() options: ForgeSwitcherOption[] = [];
  @Input() value: string | null | undefined = null;
  /** Heading above the list, e.g. "Your heroes". */
  @Input() listLabel = 'Choose';
  /** Used in labels: "Active hero: Edrann. Change hero". */
  @Input() noun = 'item';
  /** Trigger text when nothing is selected. */
  @Input() emptyTitle = 'Nothing selected';
  @Input() emptyBadge = '⚔';

  @Output() valueChange = new EventEmitter<string>();

  @ViewChild('trigger', { read: ElementRef }) private trigger?: ElementRef<HTMLButtonElement>;
  @ViewChild(CdkListbox) private listbox?: CdkListbox<string>;

  open = false;
  panelWidth = 0;

  readonly positions: ConnectedPosition[] = [
    { originX: 'start', originY: 'bottom', overlayX: 'start', overlayY: 'top', offsetY: 6 },
    { originX: 'start', originY: 'top', overlayX: 'start', overlayY: 'bottom', offsetY: -6 },
  ];

  constructor(private cdr: ChangeDetectorRef) {}

  get selected(): ForgeSwitcherOption | undefined {
    return this.options.find((option) => option.id === this.value);
  }

  initialOf(option: ForgeSwitcherOption): string {
    return option.badge || (option.title || '?').trim().charAt(0).toUpperCase();
  }

  toggle(): void {
    if (this.open) {
      this.close();
      return;
    }
    // The list matches the trigger's width (never narrower), like a native select.
    this.panelWidth = this.trigger?.nativeElement.offsetWidth ?? 0;
    this.open = true;
  }

  close(restoreFocus = false): void {
    if (!this.open) return;
    this.open = false;
    this.cdr.markForCheck();
    if (restoreFocus) {
      this.trigger?.nativeElement.focus();
    }
  }

  onAttached(): void {
    // Hand the keyboard to the list: arrows move, Enter/Space picks, typing jumps.
    setTimeout(() => this.listbox?.focus());
  }

  onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.preventDefault();
      this.close(true);
    } else if (event.key === 'Tab') {
      this.close();
    }
  }

  onPicked(event: ListboxValueChangeEvent<string>): void {
    const id = event.value[0];
    if (id && id !== this.value) {
      this.valueChange.emit(id);
    }
    this.close(true);
  }

  /**
   * Re-picking the option that is already active changes nothing, so the listbox
   * emits no value change; close anyway, after the listbox has handled the event.
   */
  onSelectionGesture(): void {
    setTimeout(() => this.close(true));
  }
}
