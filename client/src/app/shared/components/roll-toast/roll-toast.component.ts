import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RollToastService } from '../../../core/services/roll-toast.service';
import { ForgeBadgeComponent, ForgeButtonDirective } from '../../ui';

@Component({
  selector: 'app-roll-toast',
  standalone: true,
  imports: [CommonModule, ForgeBadgeComponent, ForgeButtonDirective],
  templateUrl: './roll-toast.component.html',
  styleUrl: './roll-toast.component.css',
})
export class RollToastComponent implements OnInit {
  isRolling = false;

  constructor(public rollService: RollToastService) {}

  ngOnInit() {
    this.isRolling = true;
    setTimeout(() => {
      this.isRolling = false;
    }, 300);
  }
}
