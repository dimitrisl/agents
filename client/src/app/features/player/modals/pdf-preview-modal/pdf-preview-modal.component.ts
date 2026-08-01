import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { ForgeButtonDirective, ForgeModalComponent } from '../../../../shared/ui';

@Component({
  selector: 'app-pdf-preview-modal',
  standalone: true,
  imports: [CommonModule, ForgeButtonDirective, ForgeModalComponent],
  templateUrl: './pdf-preview-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PdfPreviewModalComponent {
  @Input() open = false;
  @Input() pdfPreviewUrl: string | null = null;

  @Output() closed = new EventEmitter<void>();

  constructor(private sanitizer: DomSanitizer) {}

  get trustedPdfPreviewUrl(): SafeResourceUrl | null {
    return this.pdfPreviewUrl
      ? this.sanitizer.bypassSecurityTrustResourceUrl(this.pdfPreviewUrl)
      : null;
  }
}
