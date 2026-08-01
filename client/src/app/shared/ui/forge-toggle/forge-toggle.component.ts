import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { NgClass } from '@angular/common';

@Component({
  selector: 'forge-toggle',
  standalone: true,
  imports: [NgClass],
  templateUrl: './forge-toggle.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ForgeToggleComponent {
  @Input() checked = false;
  @Input() ariaLabel = 'Toggle setting';
  @Output() checkedChange = new EventEmitter<boolean>();

  toggle(): void {
    this.checkedChange.emit(!this.checked);
  }
}
