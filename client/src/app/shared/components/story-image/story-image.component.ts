import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  Input,
  OnChanges,
  OnDestroy,
  SimpleChanges,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subscription } from 'rxjs';
import { AssetService } from '../../../core/services/asset.service';
import { ForgeSpinnerComponent } from '../../ui';

@Component({
  selector: 'app-story-image',
  standalone: true,
  imports: [CommonModule, ForgeSpinnerComponent],
  host: { class: 'block h-full w-full' },
  template: `
    @if (loading) {
      <div class="flex h-full min-h-24 w-full items-center justify-center rounded-xl bg-tile">
        <forge-spinner size="sm" tone="accent" label="Loading image" />
      </div>
    } @else if (errored || !displaySrc) {
      <div
        class="flex h-full min-h-24 w-full flex-col items-center justify-center gap-1 rounded-xl border border-hairline bg-tile px-3 py-4 text-center text-muted"
      >
        <span class="text-title" aria-hidden="true">🖼️</span>
        <span class="text-micro uppercase">
          {{ errored ? 'Image failed to load' : emptyLabel }}
        </span>
      </div>
    } @else {
      <img
        [src]="displaySrc"
        [alt]="alt"
        [class]="imgClass"
        [attr.data-testid]="testId || null"
        (error)="onImgError()"
      />
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StoryImageComponent implements OnChanges, OnDestroy {
  @Input() src: string | null | undefined = '';
  @Input() alt = '';
  @Input() imgClass = 'w-full h-full object-cover rounded-xl';
  @Input() emptyLabel = 'No image set';
  @Input() testId = '';

  displaySrc = '';
  loading = false;
  errored = false;

  private objectUrl: string | null = null;
  private loadSub: Subscription | null = null;

  constructor(
    private assetService: AssetService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['src']) {
      this.resolveSource();
    }
  }

  ngOnDestroy(): void {
    this.loadSub?.unsubscribe();
    this.revokeObjectUrl();
  }

  onImgError(): void {
    this.errored = true;
    this.cdr.markForCheck();
  }

  private resolveSource(): void {
    this.loadSub?.unsubscribe();
    this.revokeObjectUrl();
    this.displaySrc = '';
    this.errored = false;

    const clean = (this.src || '').trim();
    if (!clean) {
      this.loading = false;
      this.cdr.markForCheck();
      return;
    }

    const isProtected = this.assetService.isProtectedCampaignAssetUrl(clean);
    this.loading = isProtected;
    this.cdr.markForCheck();

    this.loadSub = this.assetService.resolveDisplayImage(clean).subscribe({
      next: (res) => {
        this.loading = false;
        if (res.isObjectUrl) {
          this.objectUrl = res.src;
        }
        this.displaySrc = res.src;
        this.cdr.markForCheck();
      },
      error: () => {
        this.loading = false;
        this.errored = true;
        this.displaySrc = '';
        this.cdr.markForCheck();
      },
    });
  }

  private revokeObjectUrl(): void {
    if (this.objectUrl && typeof URL !== 'undefined' && typeof URL.revokeObjectURL === 'function') {
      URL.revokeObjectURL(this.objectUrl);
    }
    this.objectUrl = null;
  }
}
