import { ChangeDetectionStrategy, Component, EventEmitter, Output, Input } from '@angular/core';

@Component({
  selector: 'forge-list-row',
  standalone: true,
  template: `
    <button
      type="button"
      class="flex w-full min-h-12 items-center justify-between gap-3 bg-panel px-4 py-3 text-left transition-colors hover:bg-tile rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-deep"
      (click)="onClick.emit()"
    >
      <div class="flex min-w-0 flex-col">
        <span class="truncate text-body font-semibold text-ink">{{ title }}</span>
        @if (description) {
          <span class="truncate text-body-sm text-muted">{{ description }}</span>
        }
      </div>

      <div class="flex shrink-0 items-center gap-3">
        <ng-content select="[trailing]"></ng-content>
        <svg
          class="h-5 w-5 text-muted opacity-50 transition-transform group-hover:opacity-100"
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
        </svg>
      </div>
    </button>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ForgeListRowComponent {
  @Input({ required: true }) title!: string;
  @Input() description?: string;

  @Output() onClick = new EventEmitter<void>();
}
