import { ChangeDetectionStrategy, Component } from '@angular/core';

@Component({
  selector: 'forge-metric-strip',
  standalone: true,
  templateUrl: './forge-metric-strip.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    class:
      'block overflow-x-auto rounded-lg border border-hairline bg-black/20',
  },
})
export class ForgeMetricStripComponent {}
