import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  EventEmitter,
  Input,
  Output,
  QueryList,
  Directive,
  ViewChildren,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FocusKeyManager, FocusableOption } from '@angular/cdk/a11y';

export interface ForgeTab {
  id: string;
  label: string;
  disabled?: boolean;
}

type ForgeTabsVariant = 'pill' | 'underline';

let nextInstanceId = 0;

@Directive({
  selector: 'button[forgeTabButton]',
  standalone: true,
})
class ForgeTabButtonDirective implements FocusableOption {
  constructor(private elementRef: ElementRef<HTMLButtonElement>) {}

  get disabled(): boolean {
    return this.elementRef.nativeElement.disabled;
  }

  focus(): void {
    this.elementRef.nativeElement.focus();
  }
}

@Component({
  selector: 'forge-tabs',
  standalone: true,
  imports: [CommonModule, ForgeTabButtonDirective],
  templateUrl: './forge-tabs.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ForgeTabsComponent implements AfterViewInit {
  @Input() tabs: ForgeTab[] = [];
  @Input() activeId!: string;
  @Input() instanceId = `forge-tabs-${nextInstanceId++}`;
  @Input() variant: ForgeTabsVariant = 'pill';

  @Output() activeIdChange = new EventEmitter<string>();

  @ViewChildren(ForgeTabButtonDirective)
  private tabButtons!: QueryList<ForgeTabButtonDirective>;

  private keyManager?: FocusKeyManager<ForgeTabButtonDirective>;

  ngAfterViewInit(): void {
    this.keyManager = new FocusKeyManager(this.tabButtons)
      .withHorizontalOrientation('ltr')
      .withHomeAndEnd()
      .withWrap();
  }

  selectTab(tab: ForgeTab): void {
    if (tab.disabled) return;
    this.activeIdChange.emit(tab.id);
  }

  tabId(tabId: string): string {
    return `${this.instanceId}-tab-${tabId}`;
  }

  get tablistClasses(): string {
    return this.variant === 'underline'
      ? 'flex gap-2 overflow-x-auto border-b border-hairline pb-0 whitespace-nowrap [-webkit-overflow-scrolling:touch] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden'
      : 'flex gap-2 overflow-x-auto border-b border-hairline pb-0.5 whitespace-nowrap [-webkit-overflow-scrolling:touch]';
  }

  get buttonBaseClasses(): string {
    const shared =
      'shrink-0 border-b-2 px-4 py-3 text-body-sm transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-50';

    return this.variant === 'underline'
      ? shared
      : `${shared} rounded-t-lg font-semibold`;
  }

  tabClasses(tab: ForgeTab): string {
    if (this.variant === 'underline') {
      return this.activeId === tab.id
        ? 'border-accent bg-panel text-ink font-semibold'
        : 'border-transparent text-muted hover:bg-panel hover:text-ink';
    }

    return this.activeId === tab.id
      ? 'border-accent bg-accent text-white shadow-glow'
      : 'border-transparent text-muted hover:border-accent hover:bg-white/5 hover:text-accent';
  }

  onKeydown(event: KeyboardEvent, currentIndex: number): void {
    if (!this.keyManager || !this.handledKeys.has(event.key)) return;

    this.keyManager.setActiveItem(currentIndex);
    this.keyManager.onKeydown(event);
    const activeItemIndex = this.keyManager.activeItemIndex;
    if (activeItemIndex !== null && activeItemIndex !== currentIndex) {
      this.selectTab(this.tabs[activeItemIndex]);
    }
  }

  private readonly handledKeys = new Set(['ArrowRight', 'ArrowLeft', 'Home', 'End']);
}
