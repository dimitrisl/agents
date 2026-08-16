import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { ForgeTab, ForgeTabsComponent } from '../../../shared/ui';

@Component({
  selector: 'app-character-tabs',
  standalone: true,
  imports: [ForgeTabsComponent],
  templateUrl: './character-tabs.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CharacterTabsComponent {
  @Input() tabs: ForgeTab[] = [];
  @Input() activeId!: string;

  @Output() activeIdChange = new EventEmitter<string>();
}
