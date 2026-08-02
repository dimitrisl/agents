import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

@Component({
  selector: 'forge-metric',
  standalone: true,
  templateUrl: './forge-metric.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    class: 'block shrink-0',
  },
})
export class ForgeMetricComponent {
  @Input({ required: true }) label!: string;
  @Input({ required: true }) value!: string | number;
  @Input() icon?: string;
}
