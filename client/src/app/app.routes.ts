import { Routes } from '@angular/router';
import { LoginComponent } from './features/auth/login.component';
import { authGuard } from './core/guards/auth.guard';
import { adminGuard } from './core/guards/admin.guard';

// Login is the entry page, so it ships in the main bundle. Every other page is
// lazy: its code downloads on first visit instead of with the app shell.
export const routes: Routes = [
  { path: 'login', component: LoginComponent },
  {
    path: 'campaigns',
    loadComponent: () =>
      import('./features/campaigns/campaign-picker.component').then((m) => m.CampaignPickerComponent),
    canActivate: [authGuard],
  },
  {
    path: 'player',
    loadComponent: () => import('./features/player/player.component').then((m) => m.PlayerComponent),
    canActivate: [authGuard],
  },
  {
    path: 'forge',
    loadComponent: () => import('./features/forge/forge.component').then((m) => m.ForgeComponent),
    canActivate: [authGuard],
  },
  {
    path: 'dm',
    loadComponent: () => import('./features/dm/dm.component').then((m) => m.DmComponent),
    canActivate: [authGuard],
  },
  {
    path: 'rules',
    loadComponent: () => import('./features/rules/rules.component').then((m) => m.RulesComponent),
    canActivate: [authGuard],
  },
  {
    path: 'settings',
    loadComponent: () => import('./features/settings/settings.component').then((m) => m.SettingsComponent),
    canActivate: [authGuard],
  },
  {
    path: 'faq',
    loadComponent: () => import('./features/faq/faq.component').then((m) => m.FaqComponent),
    canActivate: [authGuard],
  },
  {
    path: 'admin',
    loadComponent: () => import('./features/admin/admin.component').then((m) => m.AdminComponent),
    canActivate: [authGuard, adminGuard],
  },
  { path: '', redirectTo: '/campaigns', pathMatch: 'full' },
  {
    path: '**',
    loadComponent: () => import('./features/not-found/not-found.component').then((m) => m.NotFoundComponent),
  },
];
