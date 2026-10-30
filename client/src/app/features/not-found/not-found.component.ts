import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { ForgeButtonDirective, ForgeEmptyStateComponent, ForgePageComponent } from '../../shared/ui';

/**
 * Unknown URLs land here instead of bouncing to /login, which logged-in users
 * read as "I got signed out".
 */
@Component({
  selector: 'app-not-found',
  standalone: true,
  imports: [RouterLink, ForgeButtonDirective, ForgeEmptyStateComponent, ForgePageComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <forge-page>
      <forge-empty-state
        icon="🧭"
        title="This path leads nowhere"
        description="The page you were looking for does not exist or has moved."
      >
        <div class="mt-2 flex justify-center">
          @if (auth.hasToken()) {
            <a forgeButton variant="primary" size="lg" routerLink="/campaigns">Back to your campaigns</a>
          } @else {
            <a forgeButton variant="primary" size="lg" routerLink="/login">Go to login</a>
          }
        </div>
      </forge-empty-state>
    </forge-page>
  `,
})
export class NotFoundComponent {
  constructor(public auth: AuthService) {}
}
