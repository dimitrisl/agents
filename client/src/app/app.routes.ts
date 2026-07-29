import { Routes } from '@angular/router';
import { LoginComponent } from './features/auth/login.component';
import { PlayerComponent } from './features/player/player.component';
import { DmComponent } from './features/dm/dm.component';
import { RulesComponent } from './features/rules/rules.component';

export const routes: Routes = [
  { path: 'login', component: LoginComponent },
  { path: 'player', component: PlayerComponent },
  { path: 'dm', component: DmComponent },
  { path: 'rules', component: RulesComponent },
  { path: '', redirectTo: '/player', pathMatch: 'full' },
  { path: '**', redirectTo: '/player' },
];
