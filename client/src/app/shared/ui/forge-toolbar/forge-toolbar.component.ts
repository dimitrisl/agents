import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

type ForgeToolbarCollapseAt = 'sm' | 'md' | 'lg';

const COLLAPSE_CLASSES: Record<ForgeToolbarCollapseAt, string> = {
  sm: 'flex-col items-stretch sm:flex-row sm:items-center',
  md: 'flex-col items-stretch md:flex-row md:items-center',
  lg: 'flex-col items-stretch lg:flex-row lg:items-center',
};

@Component({
  selector: 'forge-toolbar',
  standalone: true,
  templateUrl: './forge-toolbar.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '[class]': 'classes',
  },
})
export class ForgeToolbarComponent {
  @Input() collapseAt: ForgeToolbarCollapseAt = 'md';

  get classes(): string {
    return [
      'flex min-h-14 gap-3 border-b border-hairline py-2',
      COLLAPSE_CLASSES[this.collapseAt],
    ].join(' ');
  }
}
