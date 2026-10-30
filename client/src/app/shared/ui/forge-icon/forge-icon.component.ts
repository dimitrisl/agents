import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

export type ForgeIconName = 'close' | 'chevron-down' | 'check' | 'plus' | 'minus' | 'sliders' | 'pencil';
type ForgeIconSize = 'xs' | 'sm' | 'md' | 'lg';

const SIZE_CLASSES: Record<ForgeIconSize, string> = {
  xs: 'h-3 w-3',
  sm: 'h-4 w-4',
  md: 'h-5 w-5',
  lg: 'h-6 w-6',
};

/**
 * Stroke icons drawn in `currentColor`, so they follow the button's text color
 * and the edition accent. Decorative only: the button carries the aria-label.
 *
 * Use instead of text glyphs such as "×" / "✕", which render at x-height and
 * look a few pixels wide.
 */
@Component({
  selector: 'forge-icon',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '[class]': 'classes',
    'aria-hidden': 'true',
  },
  template: `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round" class="h-full w-full">
      @switch (name) {
        @case ('close') {
          <path d="M6 6l12 12M18 6L6 18" />
        }
        @case ('chevron-down') {
          <path d="M6 9l6 6 6-6" />
        }
        @case ('check') {
          <path d="M5 12.5l4.5 4.5L19 7.5" />
        }
        @case ('plus') {
          <path d="M12 5v14M5 12h14" />
        }
        @case ('minus') {
          <path d="M5 12h14" />
        }
        @case ('sliders') {
          <path d="M4 7h9M17 7h3M4 17h3M11 17h9" />
          <circle cx="15" cy="7" r="2" />
          <circle cx="9" cy="17" r="2" />
        }
        @case ('pencil') {
          <path d="M4 20h4L18.5 9.5a2.1 2.1 0 0 0-4-4L4 16v4z" />
          <path d="M13.5 6.5l4 4" />
        }
      }
    </svg>
  `,
})
export class ForgeIconComponent {
  @Input({ required: true }) name!: ForgeIconName;
  @Input() size: ForgeIconSize = 'md';

  get classes(): string {
    return `inline-block shrink-0 ${SIZE_CLASSES[this.size]}`;
  }
}
