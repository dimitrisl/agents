import { Directive, Input, booleanAttribute } from '@angular/core';

type ForgeButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
type ForgeButtonSize = 'sm' | 'md' | 'lg';
type ForgeButtonTone = 'accent' | 'danger' | 'success';

const BASE_CLASSES =
  'inline-flex items-center justify-center gap-2 font-semibold transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-deep disabled:pointer-events-none';

const VARIANT_CLASSES: Record<ForgeButtonVariant, string> = {
  primary:
    'border border-accent bg-[linear-gradient(135deg,color-mix(in_srgb,var(--theme-accent)_25%,transparent),color-mix(in_srgb,var(--theme-accent)_8%,transparent))] text-ink shadow-none [text-shadow:0_1px_2px_rgba(0,0,0,0.5)] hover:-translate-y-0.5 hover:bg-accent hover:text-white hover:shadow-glow active:translate-y-0',
  // Colors for secondary live in SECONDARY_NEUTRAL_CLASSES / SECONDARY_TONE_CLASSES so a tone replaces them
  // instead of stacking conflicting utilities on top.
  secondary: 'border hover:-translate-y-px active:translate-y-0',
  ghost:
    'border border-transparent bg-transparent text-muted hover:bg-white/5 hover:text-ink active:translate-y-0',
  danger:
    'border border-red/60 bg-red/10 text-red hover:-translate-y-px hover:border-red hover:bg-red hover:text-white active:translate-y-0',
};

const SECONDARY_NEUTRAL_CLASSES =
  'border-hairline bg-white/5 text-muted hover:border-white/30 hover:bg-white/10 hover:text-ink';

const SECONDARY_TONE_CLASSES: Record<ForgeButtonTone, string> = {
  accent:
    'border-accent/70 bg-white/5 text-accent hover:border-accent hover:bg-accent hover:text-white',
  // Tinted, never a saturated fill (design-contract §3): for paired actions such as
  // Damage / Heal where the color carries meaning next to an icon or label.
  danger: 'border-red/25 bg-red/5 text-red hover:border-red/60 hover:bg-red/15',
  success: 'border-emerald/25 bg-emerald/5 text-emerald hover:border-emerald/60 hover:bg-emerald/15',
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
    // attr.* so the binding is valid on <a forgeButton> as well as <button>.
    '[attr.disabled]': 'disabled || loading ? "" : null',
    '[attr.aria-busy]': 'loading || null',
  },
})
export class ForgeButtonDirective {
  @Input() variant: ForgeButtonVariant = 'primary';
  @Input() size: ForgeButtonSize = 'md';
  @Input({ transform: booleanAttribute }) fullWidth = false;
  @Input({ transform: booleanAttribute }) iconOnly = false;
  @Input() tone?: ForgeButtonTone;
  /**
   * Joins two buttons into one split control (e.g. "Cast" + "▾"): `start` squares
   * the right corners, `end` the left ones and overlaps the shared border.
   */
  @Input() attach?: 'start' | 'end';
  /** Shows a leading spinner and disables the button, e.g. while a request runs. */
  @Input({ transform: booleanAttribute }) loading = false;
  /** Owns `[disabled]` so it can be combined with `loading`; behaves like the native one. */
  @Input({ transform: booleanAttribute }) disabled = false;

  get classes(): string {
    return [
      BASE_CLASSES,
      VARIANT_CLASSES[this.variant],
      this.variant === 'secondary'
        ? this.tone
          ? SECONDARY_TONE_CLASSES[this.tone]
          : SECONDARY_NEUTRAL_CLASSES
        : '',
      this.iconOnly ? ICON_SIZE_CLASSES[this.size] : SIZE_CLASSES[this.size],
      this.fullWidth ? 'w-full' : '',
      this.attach === 'start' ? 'rounded-l-lg' : this.attach === 'end' ? '-ml-px rounded-r-lg' : 'rounded-lg',
      // A loading button stays fully opaque so the spinner and label read clearly.
      this.loading ? 'forge-btn-loading' : 'disabled:opacity-50',
    ].join(' ');
  }
}
