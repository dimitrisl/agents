import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Input,
  OnChanges,
  OnDestroy,
  Output,
  SimpleChanges,
  TemplateRef,
  ViewChild,
} from '@angular/core';
import { Dialog, DialogModule, DialogRef } from '@angular/cdk/dialog';
import { ForgeButtonDirective } from '../forge-button/forge-button.directive';

@Component({
  selector: 'forge-modal',
  standalone: true,
  imports: [DialogModule, ForgeButtonDirective],
  templateUrl: './forge-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ForgeModalComponent implements AfterViewInit, OnChanges, OnDestroy {
  @Input() open = false;
  @Input() title?: string;
  @Input() maxWidth = '560px';

  @Output() openChange = new EventEmitter<boolean>();
  @Output() closed = new EventEmitter<void>();

  @ViewChild('modalTemplate') private modalTemplate!: TemplateRef<unknown>;

  private dialogRef?: DialogRef<void>;
  private viewReady = false;

  constructor(private dialog: Dialog) {}

  ngAfterViewInit(): void {
    this.viewReady = true;
    this.syncDialog();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['open']) {
      this.syncDialog();
    }
  }

  ngOnDestroy(): void {
    this.dialogRef?.close();
  }

  close(): void {
    this.dialogRef?.close();
  }

  private syncDialog(): void {
    if (!this.viewReady) return;

    if (this.open && !this.dialogRef) {
      this.dialogRef = this.dialog.open(this.modalTemplate, {
        width: `min(92vw, ${this.maxWidth})`,
        maxWidth: '92vw',
        maxHeight: '85vh',
        restoreFocus: true,
        autoFocus: 'first-tabbable',
      });

      this.dialogRef.closed.subscribe(() => {
        this.dialogRef = undefined;
        this.openChange.emit(false);
        this.closed.emit();
      });
    } else if (!this.open && this.dialogRef) {
      this.dialogRef.close();
    }
  }
}
