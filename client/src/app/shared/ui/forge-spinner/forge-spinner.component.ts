import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

type ForgeSpinnerSize = 'sm' | 'md' | 'lg';
type ForgeSpinnerTone = 'accent' | 'current';

const SIZE_CLASSES: Record<ForgeSpinnerSize, string> = {
  sm: 'h-4 w-4',
  md: 'h-6 w-6',
  lg: 'h-10 w-10',
};

const TONE_CLASSES: Record<ForgeSpinnerTone, string> = {
  accent: 'text-accent',
  current: '',
};

/** Indeterminate progress. Announces `label` to screen readers via role="status". */
@Component({
  selector: 'forge-spinner',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    role: 'status',
    class: 'inline-flex items-center justify-center',
  },
  template: `
    <svg
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      [class]="svgClasses"
    >
      <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="3" class="opacity-20" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" stroke-width="3" stroke-linecap="round" />
    </svg>
    <span class="sr-only">{{ label }}</span>
  `,
})
export class ForgeSpinnerComponent {
  @Input() size: ForgeSpinnerSize = 'md';
  @Input() tone: ForgeSpinnerTone = 'accent';
  @Input() label = 'Loading';

  get svgClasses(): string {
    // Slowed rather than stopped under reduced motion: it is the only progress cue.
    return `animate-spin motion-reduce:[animation-duration:2s] ${SIZE_CLASSES[this.size]} ${TONE_CLASSES[this.tone]}`;
  }
}
