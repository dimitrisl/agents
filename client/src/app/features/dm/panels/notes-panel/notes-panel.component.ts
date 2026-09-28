import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output, OnInit, OnDestroy } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subject, Subscription } from 'rxjs';
import { debounceTime } from 'rxjs/operators';
import { ForgeButtonDirective, ForgeTextareaDirective } from '../../../../shared/ui';

@Component({
  selector: 'app-notes-panel',
  standalone: true,
  imports: [FormsModule, ForgeButtonDirective, ForgeTextareaDirective],
  templateUrl: './notes-panel.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class NotesPanelComponent implements OnInit, OnDestroy {
  @Input() campaignNotes = '';

  @Output() campaignNotesChange = new EventEmitter<string>();
  @Output() saveNotes = new EventEmitter<void>();

  private notesSubject = new Subject<string>();
  private sub?: Subscription;

  ngOnInit() {
    this.sub = this.notesSubject.pipe(debounceTime(1500)).subscribe((notes) => {
      this.campaignNotesChange.emit(notes);
      this.saveNotes.emit();
    });
  }

  ngOnDestroy() {
    this.sub?.unsubscribe();
  }

  onNotesChange(newNotes: string) {
    this.campaignNotes = newNotes;
    this.notesSubject.next(newNotes);
  }
}
