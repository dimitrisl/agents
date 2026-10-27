import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  EventEmitter,
  Input,
  OnChanges,
  Output,
  SimpleChanges,
  inject,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  ForgeButtonDirective,
  ForgeInputDirective,
  ForgeModalComponent,
  ForgeTextareaDirective,
} from '../../../../shared/ui';

@Component({
  selector: 'app-portrait-modal',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeButtonDirective,
    ForgeInputDirective,
    ForgeModalComponent,
    ForgeTextareaDirective,
  ],
  templateUrl: './portrait-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PortraitModalComponent implements OnChanges {
  private readonly cdr = inject(ChangeDetectorRef);

  @Input() open = false;
  @Input() currentPortraitUrl: string = '';
  @Input() portraitPrompt = '';

  @Output() openChange = new EventEmitter<boolean>();
  @Output() portraitPromptChange = new EventEmitter<string>();
  @Output() generateAiPortrait = new EventEmitter<void>();
  @Output() savePortraitUrl = new EventEmitter<string>();
  @Output() uploadPortraitFile = new EventEmitter<File>();

  activeTab: 'url' | 'upload' | 'ai' = 'url';

  // URL Tab State
  urlInput = '';
  urlPreviewFailed = false;

  // Upload Tab State
  selectedFile: File | null = null;
  filePreviewUrl: string | null = null;
  isDragging = false;
  uploadError: string | null = null;

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['open'] && this.open) {
      this.urlInput = this.currentPortraitUrl || '';
      this.urlPreviewFailed = false;
      this.selectedFile = null;
      if (this.filePreviewUrl) {
        URL.revokeObjectURL(this.filePreviewUrl);
        this.filePreviewUrl = null;
      }
      this.uploadError = null;
      this.isDragging = false;
    }
  }

  selectTab(tab: 'url' | 'upload' | 'ai'): void {
    this.activeTab = tab;
  }

  onUrlChange(newVal: string): void {
    this.urlInput = newVal;
    this.urlPreviewFailed = false;
  }

  onUrlError(): void {
    if (this.urlInput.trim()) {
      this.urlPreviewFailed = true;
    }
  }

  applyUrl(): void {
    const trimmed = this.urlInput.trim();
    if (!trimmed) return;
    this.savePortraitUrl.emit(trimmed);
  }

  clearPortrait(): void {
    this.savePortraitUrl.emit('');
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.handleFile(input.files[0]);
    }
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging = true;
  }

  onDragLeave(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging = false;
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging = false;
    if (event.dataTransfer?.files && event.dataTransfer.files.length > 0) {
      this.handleFile(event.dataTransfer.files[0]);
    }
  }

  clearSelectedFile(event?: Event): void {
    if (event) {
      event.stopPropagation();
    }
    if (this.filePreviewUrl) {
      URL.revokeObjectURL(this.filePreviewUrl);
      this.filePreviewUrl = null;
    }
    this.selectedFile = null;
    this.uploadError = null;
    this.cdr.markForCheck();
  }

  applyUpload(): void {
    if (!this.selectedFile) return;
    this.uploadPortraitFile.emit(this.selectedFile);
  }

  applyAi(): void {
    this.generateAiPortrait.emit();
  }

  private handleFile(file: File): void {
    if (!file.type.startsWith('image/')) {
      this.uploadError = 'Please select a valid image file (PNG, JPG, WEBP, or GIF).';
      this.cdr.markForCheck();
      return;
    }

    const maxSize = 10 * 1024 * 1024; // 10MB
    if (file.size > maxSize) {
      this.uploadError = 'File size exceeds 10MB limit.';
      this.cdr.markForCheck();
      return;
    }

    if (this.filePreviewUrl) {
      URL.revokeObjectURL(this.filePreviewUrl);
    }

    this.selectedFile = file;
    this.filePreviewUrl = URL.createObjectURL(file);
    this.uploadError = null;
    this.cdr.markForCheck();
  }
}
