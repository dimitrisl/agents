import { ChangeDetectionStrategy, Component, EventEmitter, Input, OnChanges, OnDestroy, OnInit, Output, SimpleChanges } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subject, Subscription, timer } from 'rxjs';
import { map, switchMap, takeUntil } from 'rxjs/operators';
import { ForgeButtonDirective, ForgeTextareaDirective } from '../../../../shared/ui';

@Component({
  selector: 'app-notes-panel',
  standalone: true,
  imports: [FormsModule, ForgeButtonDirective, ForgeTextareaDirective],
  templateUrl: './notes-panel.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class NotesPanelComponent implements OnInit, OnChanges, OnDestroy {
  @Input() campaignName = '';
  @Input() campaignNotes = '';

  @Output() campaignNotesChange = new EventEmitter<string>();
  @Output() saveNotes = new EventEmitter<void>();

  private notesSubject = new Subject<string>();
  private cancelPending$ = new Subject<void>();
  private sub?: Subscription;
  private hasPendingNotes = false;

  ngOnInit() {
    this.sub = this.notesSubject
      .pipe(
        switchMap((notes) =>
          timer(1500).pipe(
            takeUntil(this.cancelPending$),
            map(() => notes)
          )
        )
      )
      .subscribe((notes) => {
        this.hasPendingNotes = false;
        this.campaignNotesChange.emit(notes);
        this.saveNotes.emit();
      });
  }

  ngOnChanges(changes: SimpleChanges) {
    if (changes['campaignName'] && !changes['campaignName'].firstChange) {
      // Drop any pending debounce from the previously selected campaign so it never overwrites the new one.
      this.hasPendingNotes = false;
      this.cancelPending$.next();
    }
  }

  ngOnDestroy() {
    if (this.hasPendingNotes) {
      this.hasPendingNotes = false;
      this.campaignNotesChange.emit(this.campaignNotes);
      this.saveNotes.emit();
    }
    this.cancelPending$.next();
    this.cancelPending$.complete();
    this.sub?.unsubscribe();
  }

  /** Returns and clears unsaved draft notes if a debounced save is pending (used before switching campaign). */
  consumePendingNotes(): string | null {
    if (!this.hasPendingNotes) return null;
    this.hasPendingNotes = false;
    this.cancelPending$.next();
    return this.campaignNotes;
  }

  onNotesChange(newNotes: string) {
    this.campaignNotes = newNotes;
    this.hasPendingNotes = true;
    this.notesSubject.next(newNotes);
  }
}
