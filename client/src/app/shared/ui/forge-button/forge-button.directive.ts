import { Directive, Input, booleanAttribute } from '@angular/core';

type ForgeButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
type ForgeButtonSize = 'sm' | 'md' | 'lg';
type ForgeButtonTone = 'accent';

const BASE_CLASSES =
  'inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-deep disabled:pointer-events-none disabled:opacity-50';

const VARIANT_CLASSES: Record<ForgeButtonVariant, string> = {
  primary:
    'border border-accent bg-[linear-gradient(135deg,color-mix(in_srgb,var(--theme-accent)_25%,transparent),color-mix(in_srgb,var(--theme-accent)_8%,transparent))] text-ink shadow-none [text-shadow:0_1px_2px_rgba(0,0,0,0.5)] hover:-translate-y-0.5 hover:bg-accent hover:text-white hover:shadow-glow active:translate-y-0',
  secondary:
    'border border-hairline bg-white/5 text-muted hover:-translate-y-px hover:border-white/30 hover:bg-white/10 hover:text-ink active:translate-y-0',
  ghost:
    'border border-transparent bg-transparent text-muted hover:bg-white/5 hover:text-ink active:translate-y-0',
  danger:
    'border border-red/60 bg-red/10 text-red hover:-translate-y-px hover:border-red hover:bg-red hover:text-white active:translate-y-0',
};

const SECONDARY_TONE_CLASSES: Record<ForgeButtonTone, string> = {
  accent:
    'border-accent/70 text-accent hover:border-accent hover:bg-accent hover:text-white',
};

const SIZE_CLASSES: Record<ForgeButtonSize, string> = {
  sm: 'min-h-8 px-2.5 py-1 text-label',
  md: 'min-h-10 px-5 py-2.5 text-body',
  lg: 'min-h-12 px-6 py-3 text-title',
};

const ICON_SIZE_CLASSES: Record<ForgeButtonSize, string> = {
  sm: 'h-7 min-h-7 w-7 p-0 text-label',
  md: 'h-9 min-h-9 w-9 p-0 text-body',
  lg: 'h-11 min-h-11 w-11 p-0 text-title',
};

@Directive({
  selector: 'button[forgeButton], a[forgeButton]',
  standalone: true,
  host: {
    '[class]': 'classes',
  },
})
export class ForgeButtonDirective {
  @Input() variant: ForgeButtonVariant = 'primary';
  @Input() size: ForgeButtonSize = 'md';
  @Input({ transform: booleanAttribute }) fullWidth = false;
  @Input({ transform: booleanAttribute }) iconOnly = false;
  @Input() tone?: ForgeButtonTone;

  get classes(): string {
    return [
      BASE_CLASSES,
      VARIANT_CLASSES[this.variant],
      this.variant === 'secondary' && this.tone
        ? SECONDARY_TONE_CLASSES[this.tone]
        : '',
      this.iconOnly ? ICON_SIZE_CLASSES[this.size] : SIZE_CLASSES[this.size],
      this.fullWidth ? 'w-full' : '',
    ].join(' ');
  }
}
