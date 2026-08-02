import { Directive, Input, booleanAttribute } from '@angular/core';

const BASE_CLASSES =
  'w-full rounded-lg border border-hairline bg-black/45 px-3.5 py-2.5 text-body text-ink transition-all duration-200 placeholder:text-muted/70 focus:border-accent focus:bg-black/65 focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-deep disabled:cursor-not-allowed disabled:opacity-50';

const INVALID_CLASSES =
  'border-red text-red focus:border-red focus:ring-red';

@Directive({
  selector: 'input[forgeInput]',
  standalone: true,
  host: {
    '[class]': 'classes',
  },
})
export class ForgeInputDirective {
  @Input({ transform: booleanAttribute }) invalid = false;

  get classes(): string {
    return [BASE_CLASSES, this.invalid ? INVALID_CLASSES : ''].join(' ');
  }
}
