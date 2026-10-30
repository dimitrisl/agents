import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

type ForgeSkeletonShape = 'text' | 'block' | 'circle';

/**
 * Placeholder for content that is still loading. Decorative: put `aria-busy="true"`
 * on the region it stands in for. Size `block` / `circle` with classes on the host,
 * e.g. `<forge-skeleton shape="block" class="h-32" />`.
 */
@Component({
  selector: 'forge-skeleton',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    'aria-hidden': 'true',
    '[class]': 'hostClasses',
  },
  template: `
    @if (shape === 'text') {
      @for (line of lineIndexes; track line; let last = $last) {
        <span [class]="lineClasses(last)"></span>
      }
    }
  `,
})
export class ForgeSkeletonComponent {
  @Input() shape: ForgeSkeletonShape = 'text';
  /** Number of text lines; the last one is shortened like a paragraph end. */
  @Input() lines = 1;

  get lineIndexes(): number[] {
    return Array.from({ length: Math.max(1, this.lines) }, (_, i) => i);
  }

  lineClasses(last: boolean): string {
    const width = last && this.lines > 1 ? 'w-3/5' : 'w-full';
    return `block h-3 rounded bg-tile animate-pulse motion-reduce:animate-none ${width}`;
  }

  get hostClasses(): string {
    if (this.shape === 'text') return 'flex w-full flex-col gap-2';
    const shapeClasses = this.shape === 'circle' ? 'rounded-full' : 'w-full rounded-xl';
    return `block shrink-0 bg-tile animate-pulse motion-reduce:animate-none ${shapeClasses}`;
  }
}
