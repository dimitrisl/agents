import { Directive, Input, booleanAttribute } from '@angular/core';

const BASE_CLASSES =
  'w-full appearance-none rounded-lg border border-hairline bg-black/45 bg-no-repeat text-ink transition-all duration-200 focus:border-accent focus:bg-black/65 focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-deep disabled:cursor-not-allowed disabled:opacity-50';

// Padding, arrow position and text size, kept out of BASE_CLASSES so `dense`
// replaces them instead of fighting them with !important overrides.
const SIZE_CLASSES = 'bg-[right_0.75rem_center] px-3.5 py-2.5 pr-10 text-body';
const DENSE_CLASSES = 'bg-[right_0.5rem_center] px-2.5 py-1.5 pr-8 text-label';

const INVALID_CLASSES =
  'border-red text-red focus:border-red focus:ring-red';

@Directive({
  selector: 'select[forgeSelect]',
  standalone: true,
  host: {
    '[class]': 'classes',
  },
})
export class ForgeSelectDirective {
  @Input({ transform: booleanAttribute }) invalid = false;
  /** Compact control for dense editors (e.g. the weapon breakdown panel). */
  @Input({ transform: booleanAttribute }) dense = false;

  get classes(): string {
    return [
      BASE_CLASSES,
      this.dense ? DENSE_CLASSES : SIZE_CLASSES,
      this.invalid ? INVALID_CLASSES : '',
    ].join(' ');
  }
}
