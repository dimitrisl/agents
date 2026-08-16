import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

@Component({
  selector: 'forge-empty-state',
  standalone: true,
  templateUrl: './forge-empty-state.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    class: 'block',
  },
})
export class ForgeEmptyStateComponent {
  @Input() icon?: string;
  @Input({ required: true }) title!: string;
  @Input() description?: string;
}
