import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

@Component({
  selector: 'forge-page',
  standalone: true,
  templateUrl: './forge-page.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ForgePageComponent {
  @Input() title?: string;
  @Input() subtitle?: string;
}
