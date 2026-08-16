import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output, TemplateRef } from '@angular/core';
import { NgTemplateOutlet } from '@angular/common';
import { ForgeButtonDirective, ForgeCardComponent } from '../../../shared/ui';

@Component({
  selector: 'app-choice-view',
  standalone: true,
  imports: [ForgeButtonDirective, ForgeCardComponent, NgTemplateOutlet],
  templateUrl: './choice-view.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    class: 'block w-full max-w-lg',
  },
})
export class ChoiceViewComponent {
  @Input({ required: true }) logoTemplate!: TemplateRef<unknown>;
  @Output() chooseTutorial = new EventEmitter<void>();
  @Output() chooseAuth = new EventEmitter<void>();
  @Output() quickDemo = new EventEmitter<'mitsos' | 'guest'>();
}
