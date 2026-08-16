import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

type ForgeBadgeTone = 'accent' | 'muted' | 'gold' | 'danger' | 'success';
type ForgeBadgeSize = 'sm' | 'md';

const BASE_CLASSES =
  'inline-flex items-center justify-center gap-1 rounded-md border font-semibold uppercase tracking-[0.03em] transition-colors duration-200';

const TONE_CLASSES: Record<ForgeBadgeTone, string> = {
  accent: 'border-accent/40 bg-accent/10 text-accent',
  muted: 'border-muted/30 bg-muted/10 text-muted',
  gold: 'border-gold/40 bg-gold/10 text-gold',
  danger: 'border-red/40 bg-red/10 text-red',
  success: 'border-emerald/40 bg-emerald/10 text-emerald',
};

const SIZE_CLASSES: Record<ForgeBadgeSize, string> = {
  sm: 'px-2 py-0.5 text-label',
  md: 'px-3 py-1 text-body',
};

const INTERACTIVE_CLASSES =
  'cursor-pointer hover:border-accent hover:bg-accent/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-deep';

@Component({
  selector: 'forge-badge',
  standalone: true,
  templateUrl: './forge-badge.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '[class]': 'classes',
  },
})
export class ForgeBadgeComponent {
  @Input() tone: ForgeBadgeTone = 'accent';
  @Input() size: ForgeBadgeSize = 'sm';
  @Input() interactive = false;

  get classes(): string {
    return [
      BASE_CLASSES,
      TONE_CLASSES[this.tone],
      SIZE_CLASSES[this.size],
      this.interactive ? INTERACTIVE_CLASSES : '',
    ].join(' ');
  }
}
