import { Routes } from '@angular/router';
import { LoginComponent } from './features/auth/login.component';
import { PlayerComponent } from './features/player/player.component';
import { DmComponent } from './features/dm/dm.component';
import { RulesComponent } from './features/rules/rules.component';
import { SettingsComponent } from './features/settings/settings.component';
import { AdminComponent } from './features/admin/admin.component';
import { authGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  { path: 'login', component: LoginComponent },
  { path: 'player', component: PlayerComponent, canActivate: [authGuard] },
  { path: 'dm', component: DmComponent, canActivate: [authGuard] },
  { path: 'rules', component: RulesComponent, canActivate: [authGuard] },
  { path: 'settings', component: SettingsComponent, canActivate: [authGuard] },
  { path: 'admin', component: AdminComponent, canActivate: [authGuard] },
  { path: '', redirectTo: '/login', pathMatch: 'full' },
  { path: '**', redirectTo: '/login' },
];
