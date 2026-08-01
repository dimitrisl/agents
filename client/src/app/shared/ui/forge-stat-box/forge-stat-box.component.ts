import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

type ForgeStatValueTone = 'accent' | 'success' | 'gold' | 'danger' | 'muted';

const VALUE_TONE_CLASSES: Record<ForgeStatValueTone, string> = {
  accent: 'text-accent',
  success: 'text-emerald',
  gold: 'text-gold',
  danger: 'text-red',
  muted: 'text-muted',
};

const VALUE_BASE_CLASSES = 'my-1 text-metric font-extrabold';

@Component({
  selector: 'forge-stat-box',
  standalone: true,
  templateUrl: './forge-stat-box.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    class:
      'block rounded-[10px] border border-hairline bg-black/35 p-3.5 text-center transition-all duration-200 hover:-translate-y-0.5 hover:border-hairline-hover',
  },
})
export class ForgeStatBoxComponent {
  @Input({ required: true }) label!: string;
  @Input({ required: true }) value!: string | number;
  @Input() modifier?: string;
  @Input() valueTone: ForgeStatValueTone = 'accent';

  get valueClasses(): string {
    return [VALUE_BASE_CLASSES, VALUE_TONE_CLASSES[this.valueTone]].join(' ');
  }
}
