import { ChangeDetectionStrategy, Component, Injectable, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DIALOG_DATA, Dialog, DialogRef } from '@angular/cdk/dialog';
import { firstValueFrom } from 'rxjs';
import { ForgeButtonDirective } from '../forge-button/forge-button.directive';
import { ForgeInputDirective } from '../forge-form-field/forge-input.directive';

export interface ForgeConfirmOptions {
  title: string;
  message: string;
  /** Label of the confirming button, e.g. "Delete hero". Defaults to "Confirm". */
  confirmLabel?: string;
  cancelLabel?: string;
  /** `danger` for destructive actions: red button, and Cancel gets the initial focus. */
  tone?: 'danger' | 'default';
  /** Optional text prompt mode returning entered string instead of boolean. */
  promptLabel?: string;
  promptPlaceholder?: string;
}

@Component({
  selector: 'forge-confirm-dialog',
  standalone: true,
  imports: [CommonModule, FormsModule, ForgeButtonDirective, ForgeInputDirective],
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

      @if (data.promptLabel !== undefined) {
        <div class="mt-4">
          <label for="forge-confirm-prompt-input" class="mb-1 block text-label font-semibold text-muted">
            {{ data.promptLabel }}
          </label>
          <input
            forgeInput
            id="forge-confirm-prompt-input"
            type="text"
            class="w-full"
            [placeholder]="data.promptPlaceholder || ''"
            [(ngModel)]="promptValue"
            cdkFocusInitial
          />
        </div>
      }

      <div class="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <button
          forgeButton
          variant="secondary"
          type="button"
          [attr.cdkFocusInitial]="isDanger && data.promptLabel === undefined ? '' : null"
          (click)="ref.close(data.promptLabel !== undefined ? null : false)"
        >
          {{ data.cancelLabel || 'Cancel' }}
        </button>
        <button
          forgeButton
          [variant]="isDanger ? 'danger' : 'primary'"
          type="button"
          [attr.cdkFocusInitial]="!isDanger && data.promptLabel === undefined ? '' : null"
          [disabled]="data.promptLabel !== undefined && !promptValue.trim()"
          (click)="ref.close(data.promptLabel !== undefined ? promptValue.trim() : true)"
        >
          {{ data.confirmLabel || 'Confirm' }}
        </button>
      </div>
    </section>
  `,
})
export class ForgeConfirmDialogComponent {
  readonly ref = inject<DialogRef<boolean | string | null>>(DialogRef);
  readonly data = inject<ForgeConfirmOptions>(DIALOG_DATA);
  promptValue = '';

  get isDanger(): boolean {
    return this.data.tone === 'danger';
  }
}

/**
 * Styled, accessible replacement for `window.confirm()` and `window.prompt()`.
 *
 *   if (!(await this.confirm.ask({ title: 'Delete hero?', message: '…', tone: 'danger' }))) return;
 *
 * Resolves `false` (or `null` for `askPrompt`) on Cancel, Escape or a backdrop click.
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

  askPrompt(options: ForgeConfirmOptions & { promptLabel: string }): Promise<string | null> {
    const ref = this.dialog.open<string | null, ForgeConfirmOptions>(ForgeConfirmDialogComponent, {
      data: options,
      width: 'min(92vw, 440px)',
      maxWidth: '92vw',
      restoreFocus: true,
      autoFocus: 'first-tabbable',
    });
    return firstValueFrom(ref.closed).then((result) =>
      typeof result === 'string' && result.trim() ? result.trim() : null
    );
  }
}
