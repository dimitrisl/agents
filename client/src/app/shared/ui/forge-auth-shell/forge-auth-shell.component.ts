import { ChangeDetectionStrategy, Component } from '@angular/core';

@Component({
  selector: 'forge-auth-shell',
  standalone: true,
  template: `
    <main class="flex min-h-[100dvh] items-center justify-center px-4 py-8 sm:px-6">
      <ng-content></ng-content>
    </main>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ForgeAuthShellComponent {}
