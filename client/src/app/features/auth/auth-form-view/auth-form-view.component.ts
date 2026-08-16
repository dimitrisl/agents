import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output, TemplateRef } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { NgTemplateOutlet } from '@angular/common';
import { ForgeButtonDirective, ForgeCardComponent, ForgeInputDirective } from '../../../shared/ui';

@Component({
  selector: 'app-auth-form-view',
  standalone: true,
  imports: [FormsModule, ForgeButtonDirective, ForgeCardComponent, ForgeInputDirective, NgTemplateOutlet],
  templateUrl: './auth-form-view.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    class: 'block w-full max-w-lg',
  },
})
export class AuthFormViewComponent {
  @Input({ required: true }) logoTemplate!: TemplateRef<unknown>;
  @Input() isRegister = false;
  @Input() error = '';
  @Input() username = '';
  @Input() password = '';
  @Output() usernameChange = new EventEmitter<string>();
  @Output() passwordChange = new EventEmitter<string>();
  @Output() submitAuth = new EventEmitter<void>();
  @Output() toggleMode = new EventEmitter<void>();
  @Output() back = new EventEmitter<void>();
  @Output() quickDemo = new EventEmitter<'mitsos' | 'guest'>();
}
