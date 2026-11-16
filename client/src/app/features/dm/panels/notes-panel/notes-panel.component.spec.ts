import { SimpleChange } from '@angular/core';
import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { NotesPanelComponent } from './notes-panel.component';

describe('NotesPanelComponent', () => {
  it('cancels pending debounce when switching campaigns so prior campaign notes never overwrite the new one', fakeAsync(() => {
    TestBed.configureTestingModule({
      imports: [NotesPanelComponent],
    });
    const fixture = TestBed.createComponent(NotesPanelComponent);
    const comp = fixture.componentInstance;

    const emittedNotes: string[] = [];
    let saveCalls = 0;
    comp.campaignNotesChange.subscribe((n) => emittedNotes.push(n));
    comp.saveNotes.subscribe(() => saveCalls++);

    comp.campaignName = 'Campaign A';
    comp.campaignNotes = '';
    fixture.detectChanges();

    // User types notes in Campaign A
    comp.onNotesChange('Secret A plot notes');
    tick(500);

    // Within 1500ms debounce, DM switches to Campaign B
    comp.campaignName = 'Campaign B';
    comp.campaignNotes = 'Existing B notes';
    comp.ngOnChanges({
      campaignName: new SimpleChange('Campaign A', 'Campaign B', false),
      campaignNotes: new SimpleChange('Secret A plot notes', 'Existing B notes', false),
    });

    // Advance past 1500ms: Campaign A's debounced emit must NOT fire onto Campaign B
    tick(2000);
    expect(saveCalls).toBe(0);
    expect(emittedNotes).toEqual([]);

    fixture.destroy();
  }));
});
