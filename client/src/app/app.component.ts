import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet } from '@angular/router';
import { NavbarComponent } from './shared/components/navbar/navbar.component';
import { RollToastComponent } from './shared/components/roll-toast/roll-toast.component';
import { CommandPaletteComponent } from './shared/components/command-palette/command-palette.component';
import { AuthService } from './core/services/auth.service';
import { ForgeShellComponent } from './shared/ui';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, NavbarComponent, RollToastComponent, CommandPaletteComponent, ForgeShellComponent],
  templateUrl: './app.component.html',
})
export class AppComponent {
  title = 'Phyrexian Forge';

  constructor(public authService: AuthService) {}
}
