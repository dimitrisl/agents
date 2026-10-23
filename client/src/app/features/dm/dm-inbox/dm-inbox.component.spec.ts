import { TestBed, ComponentFixture } from '@angular/core/testing';
import { DmInboxComponent } from './dm-inbox.component';
import { Whisper } from '../../../core/models/campaign.model';

describe('DmInboxComponent', () => {
  let component: DmInboxComponent;
  let fixture: ComponentFixture<DmInboxComponent>;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [DmInboxComponent],
    });

    fixture = TestBed.createComponent(DmInboxComponent);
    component = fixture.componentInstance;
  });

  it('renders whispers and emits reportWhisper event for player whispers', () => {
    const whisperFromPlayer: Whisper = {
      id: 'w_p1',
      sender: 'Krag',
      recipient: 'DM',
      message: 'Can I roll stealth?',
      timestamp: '2026-10-24 10:00:00',
      has_open_report: false,
      sender_deleted: false,
    };

    component.open = true;
    component.whispers = [whisperFromPlayer];
    component.ngOnChanges();
    fixture.detectChanges();

    const reportSpy = jest.spyOn(component.reportWhisper, 'emit');

    const reportButton: HTMLButtonElement | null = fixture.nativeElement.querySelector('button[title="Report whisper to moderators"]');
    expect(reportButton).toBeTruthy();
    expect(reportButton?.textContent).toContain('Report');

    reportButton?.click();
    expect(reportSpy).toHaveBeenCalledWith(whisperFromPlayer);
  });

  it('displays deleted user badge when sender or recipient is deleted', () => {
    const deletedUserWhisper: Whisper = {
      id: 'w_del',
      sender: 'DeletedHero',
      recipient: 'DM',
      message: 'Goodbye',
      timestamp: '2026-10-24 10:05:00',
      sender_deleted: true,
    };

    component.open = true;
    component.whispers = [deletedUserWhisper];
    component.ngOnChanges();
    fixture.detectChanges();

    const badge: HTMLElement | null = fixture.nativeElement.querySelector('.text-error');
    expect(badge).toBeTruthy();
    expect(badge?.textContent).toContain('(Διαγραμμένος χρήστης)');
  });

  it('displays Reported badge and suppresses report button when whisper is reported', () => {
    const reportedWhisper: Whisper = {
      id: 'w_rep',
      sender: 'Troublemaker',
      recipient: 'DM',
      message: 'Rude message',
      timestamp: '2026-10-24 10:10:00',
      has_open_report: true,
    };

    component.open = true;
    component.whispers = [reportedWhisper];
    component.ngOnChanges();
    fixture.detectChanges();

    const reportButton: HTMLButtonElement | null = fixture.nativeElement.querySelector('button[title="Report whisper to moderators"]');
    expect(reportButton).toBeNull();

    const reportedBadge: HTMLElement | null = fixture.nativeElement.querySelector('.text-gold');
    expect(reportedBadge).toBeTruthy();
    expect(reportedBadge?.textContent).toContain('Reported');
  });
});
