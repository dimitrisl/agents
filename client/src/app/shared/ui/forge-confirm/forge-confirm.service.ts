import { ChangeDetectionStrategy, Component, Injectable, inject } from '@angular/core';
import { DIALOG_DATA, Dialog, DialogRef } from '@angular/cdk/dialog';
import { firstValueFrom } from 'rxjs';
import { ForgeButtonDirective } from '../forge-button/forge-button.directive';

export interface ForgeConfirmOptions {
  title: string;
  message: string;
  /** Label of the confirming button, e.g. "Delete hero". Defaults to "Confirm". */
  confirmLabel?: string;
  cancelLabel?: string;
  /** `danger` for destructive actions: red button, and Cancel gets the initial focus. */
  tone?: 'danger' | 'default';
}

@Component({
  selector: 'forge-confirm-dialog',
  standalone: true,
  imports: [ForgeButtonDirective],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    role: 'alertdialog',
    'aria-modal': 'true',
    'aria-labelledby': 'forge-confirm-title',
    'aria-describedby': 'forge-confirm-message',
  },
  template: `
    <section class="rounded-[14px] border border-hairline bg-surface p-6 text-ink shadow-card">
      <h2 id="forge-confirm-title" class="font-display text-title text-ink">{{ data.title }}</h2>
      <p id="forge-confirm-message" class="mt-2 text-body text-muted">{{ data.message }}</p>

      <div class="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <button
          forgeButton
          variant="secondary"
          type="button"
          [attr.cdkFocusInitial]="isDanger ? '' : null"
          (click)="ref.close(false)"
        >
          {{ data.cancelLabel || 'Cancel' }}
        </button>
        <button
          forgeButton
          [variant]="isDanger ? 'danger' : 'primary'"
          type="button"
          [attr.cdkFocusInitial]="isDanger ? null : ''"
          (click)="ref.close(true)"
        >
          {{ data.confirmLabel || 'Confirm' }}
        </button>
      </div>
    </section>
  `,
})
export class ForgeConfirmDialogComponent {
  readonly ref = inject<DialogRef<boolean>>(DialogRef);
  readonly data = inject<ForgeConfirmOptions>(DIALOG_DATA);

  get isDanger(): boolean {
    return this.data.tone === 'danger';
  }
}

/**
 * Styled, accessible replacement for `window.confirm()`.
 *
 *   if (!(await this.confirm.ask({ title: 'Delete hero?', message: '…', tone: 'danger' }))) return;
 *
 * Resolves `false` on Cancel, Escape or a backdrop click.
 */
@Injectable({ providedIn: 'root' })
export class ForgeConfirmService {
  private readonly dialog = inject(Dialog);

  ask(options: ForgeConfirmOptions): Promise<boolean> {
    const ref = this.dialog.open<boolean, ForgeConfirmOptions>(ForgeConfirmDialogComponent, {
      data: options,
      width: 'min(92vw, 440px)',
      maxWidth: '92vw',
      restoreFocus: true,
      autoFocus: 'first-tabbable',
    });
    return firstValueFrom(ref.closed).then((result) => result === true);
  }
}
