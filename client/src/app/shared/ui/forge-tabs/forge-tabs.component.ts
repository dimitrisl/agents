import {
  AfterViewInit,
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  ElementRef,
  EventEmitter,
  HostListener,
  Input,
  OnChanges,
  Output,
  QueryList,
  SimpleChanges,
  Directive,
  ViewChild,
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
  styles: [
    `
      /* Discoverability for a horizontally scrollable tab bar: fade whichever
         edge still has tabs beyond it. The scrollbar itself stays hidden per
         the design contract (§5). These gradients are alpha masks, not palette
         colors — the tabs keep their own token colors. */
      .forge-tabs-fade-start {
        -webkit-mask-image: linear-gradient(to right, transparent 0, #000 1.5rem);
        mask-image: linear-gradient(to right, transparent 0, #000 1.5rem);
      }

      .forge-tabs-fade-end {
        -webkit-mask-image: linear-gradient(to right, #000 calc(100% - 1.5rem), transparent 100%);
        mask-image: linear-gradient(to right, #000 calc(100% - 1.5rem), transparent 100%);
      }

      .forge-tabs-fade-both {
        -webkit-mask-image: linear-gradient(
          to right,
          transparent 0,
          #000 1.5rem,
          #000 calc(100% - 1.5rem),
          transparent 100%
        );
        mask-image: linear-gradient(
          to right,
          transparent 0,
          #000 1.5rem,
          #000 calc(100% - 1.5rem),
          transparent 100%
        );
      }
    `,
  ],
})
export class ForgeTabsComponent implements AfterViewInit, OnChanges {
  @Input() tabs: ForgeTab[] = [];
  @Input() activeId!: string;
  @Input() instanceId = `forge-tabs-${nextInstanceId++}`;
  @Input() variant: ForgeTabsVariant = 'pill';

  @Output() activeIdChange = new EventEmitter<string>();

  @ViewChildren(ForgeTabButtonDirective)
  private tabButtons!: QueryList<ForgeTabButtonDirective>;

  @ViewChild('tablist')
  private tablist?: ElementRef<HTMLDivElement>;

  private keyManager?: FocusKeyManager<ForgeTabButtonDirective>;

  protected overflowStart = false;
  protected overflowEnd = false;

  constructor(private changeDetectorRef: ChangeDetectorRef) {}

  ngAfterViewInit(): void {
    this.keyManager = new FocusKeyManager(this.tabButtons)
      .withHorizontalOrientation('ltr')
      .withHomeAndEnd()
      .withWrap();

    queueMicrotask(() => this.syncOverflow());

    // Display-font swap changes label widths after first paint, which can turn a
    // fitting tab bar into a scrolling one (or the reverse).
    if (typeof document !== 'undefined') {
      (document as Document & { fonts?: FontFaceSet }).fonts?.ready?.then(() =>
        this.syncOverflow()
      );
    }
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (!changes['tabs'] && !changes['activeId']) return;

    queueMicrotask(() => {
      if (changes['activeId']) this.scrollActiveTabIntoView();
      this.syncOverflow();
    });
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

  get fadeClasses(): string {
    if (this.overflowStart && this.overflowEnd) return 'forge-tabs-fade-both';
    if (this.overflowEnd) return 'forge-tabs-fade-end';
    if (this.overflowStart) return 'forge-tabs-fade-start';
    return '';
  }

  get buttonBaseClasses(): string {
    const shared =
      'shrink-0 border-b-2 px-3 py-3 text-body transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-50 sm:px-4';

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

  onTablistScroll(): void {
    this.syncOverflow();
  }

  @HostListener('window:resize')
  onWindowResize(): void {
    this.syncOverflow();
  }

  private syncOverflow(): void {
    const element = this.tablist?.nativeElement;
    if (!element) return;

    const start = element.scrollLeft > 1;
    const end =
      Math.ceil(element.scrollLeft + element.clientWidth) < element.scrollWidth - 1;

    if (start === this.overflowStart && end === this.overflowEnd) return;

    this.overflowStart = start;
    this.overflowEnd = end;
    this.changeDetectorRef.markForCheck();
  }

  private scrollActiveTabIntoView(): void {
    const element = this.tablist?.nativeElement;
    const activeTab = element?.querySelector<HTMLElement>('[aria-selected="true"]');
    if (!activeTab) return;

    const prefersReducedMotion =
      typeof window !== 'undefined' &&
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

    activeTab.scrollIntoView({
      block: 'nearest',
      inline: 'nearest',
      behavior: prefersReducedMotion ? 'auto' : 'smooth',
    });
  }

  private readonly handledKeys = new Set(['ArrowRight', 'ArrowLeft', 'Home', 'End']);
}
