import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

type ForgeCardPadding = 'none' | 'sm' | 'md' | 'lg';

const BASE_CLASSES =
  'block rounded-[14px] border border-hairline bg-surface shadow-card backdrop-blur-lg transition-all duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]';

const PADDING_CLASSES: Record<ForgeCardPadding, string> = {
  none: 'p-0',
  sm: 'p-4',
  md: 'p-6',
  lg: 'p-8',
};

const HOVERABLE_CLASSES =
  'hover:-translate-y-0.5 hover:border-hairline-hover hover:shadow-glow';

@Component({
  selector: 'forge-card',
  standalone: true,
  templateUrl: './forge-card.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '[class]': 'classes',
  },
})
export class ForgeCardComponent {
  @Input() hoverable = true;

  // none -> p-0, sm -> p-4, md -> p-6, lg -> p-8.
  @Input() padding: ForgeCardPadding = 'md';

  get classes(): string {
    return [
      BASE_CLASSES,
      PADDING_CLASSES[this.padding],
      this.hoverable ? HOVERABLE_CLASSES : '',
    ].join(' ');
  }
}
