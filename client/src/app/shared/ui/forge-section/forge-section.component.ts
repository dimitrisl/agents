import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { NgTemplateOutlet } from '@angular/common';
import { ForgeCardComponent } from '../forge-card/forge-card.component';

type ForgeSectionVariant = 'plain' | 'card';
type ForgeSectionDensity = 'compact' | 'comfortable';

const DENSITY_CLASSES: Record<ForgeSectionDensity, string> = {
  compact: 'gap-2',
  comfortable: 'gap-4',
};

const CARD_PADDING: Record<ForgeSectionDensity, 'sm' | 'md'> = {
  compact: 'sm',
  comfortable: 'md',
};

@Component({
  selector: 'forge-section',
  standalone: true,
  imports: [ForgeCardComponent, NgTemplateOutlet],
  templateUrl: './forge-section.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '[class]': 'classes',
  },
})
export class ForgeSectionComponent {
  @Input() title?: string;
  @Input() variant: ForgeSectionVariant = 'plain';
  @Input() density: ForgeSectionDensity = 'compact';

  get classes(): string {
    return ['block', DENSITY_CLASSES[this.density]].join(' ');
  }

  get contentClasses(): string {
    return ['flex flex-col', DENSITY_CLASSES[this.density]].join(' ');
  }

  get cardPadding(): 'sm' | 'md' {
    return CARD_PADDING[this.density];
  }
}
