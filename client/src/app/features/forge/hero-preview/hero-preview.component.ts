import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CharacterSchema } from '../../../core/models/character.model';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeCardComponent,
  ForgeInputDirective,
  ForgeMetricComponent,
  ForgeMetricStripComponent,
} from '../../../shared/ui';

@Component({
  selector: 'app-hero-preview',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeCardComponent,
    ForgeInputDirective,
    ForgeMetricComponent,
    ForgeMetricStripComponent,
  ],
  templateUrl: './hero-preview.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HeroPreviewComponent {
  Math = Math;

  @Input({ required: true }) hero!: CharacterSchema;
  @Input() edition = '';
  @Input() statKeys: string[] = [];
  @Input() getClassColor!: (charClass: string) => string;
  @Input() isPrimaryStat!: (charClass: string, stat: string) => boolean;
  @Input() getModifierString!: (val: number) => string;

  @Output() accept = new EventEmitter<void>();
  @Output() discard = new EventEmitter<void>();
  @Output() regeneratePortrait = new EventEmitter<void>();
}
