import { ComponentFixture, TestBed } from '@angular/core/testing';
import { CharacterImportPanelComponent } from './character-import-panel.component';

describe('CharacterImportPanelComponent', () => {
  let fixture: ComponentFixture<CharacterImportPanelComponent>;
  let component: CharacterImportPanelComponent;

  beforeEach(() => {
    fixture = TestBed.createComponent(CharacterImportPanelComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('emits the chosen PDF file and resets the input so the same file can be picked again', () => {
    const emitted: File[] = [];
    component.pdfSelected.subscribe((f) => emitted.push(f));
    const file = new File(['%PDF'], 'sheet.pdf');
    const input = { files: [file], value: 'C:\fakepath\sheet.pdf' } as unknown as HTMLInputElement;

    component.onFile({ target: input } as unknown as Event, 'pdf');
    expect(emitted).toEqual([file]);
    expect(input.value).toBe('');
  });

  it('submits a trimmed D&D Beyond link, but not while busy or empty', () => {
    const sent: string[] = [];
    component.dndBeyondSubmitted.subscribe((u) => sent.push(u));

    component.dndBeyondUrl = '   ';
    component.submitDndBeyond();
    component.dndBeyondUrl = ' https://www.dndbeyond.com/characters/1 ';
    component.busy = true;
    component.submitDndBeyond();
    component.busy = false;
    component.submitDndBeyond();

    expect(sent).toEqual(['https://www.dndbeyond.com/characters/1']);
  });

  it('tells the player the import becomes a new hero', () => {
    expect(fixture.nativeElement.textContent).toContain('new hero');
  });
});
