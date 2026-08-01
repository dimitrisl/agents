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
