import { ComponentFixture, TestBed } from '@angular/core/testing';
import { CampaignHeaderComponent } from './campaign-header.component';

describe('CampaignHeaderComponent campaign switcher', () => {
  let fixture: ComponentFixture<CampaignHeaderComponent>;
  let component: CampaignHeaderComponent;

  beforeEach(() => {
    fixture = TestBed.createComponent(CampaignHeaderComponent);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('campaignName', 'Test');
    fixture.componentRef.setInput('userCampaigns', [{ campaign_name: 'Test' }, { campaign_name: 'Curse of Strahd' }]);
    fixture.componentRef.setInput('inviteCode', 'Na6Mq_XKN7h6Z91N');
    fixture.detectChanges();
  });

  it('shows the open campaign with its invite code, in a header-height button', () => {
    const button = fixture.nativeElement.querySelector('forge-switcher button') as HTMLButtonElement;
    expect(button.className).toContain('h-11');
    expect(button.textContent).toContain('Test');
    expect(button.textContent).toContain('Invite code · Na6Mq_XKN7h6Z91N');
  });

  it('lists every campaign; only the open one carries the invite code', () => {
    expect(component.campaignOptions).toEqual([
      { id: 'Test', title: 'Test', badge: '🏰', subtitle: 'Invite code · Na6Mq_XKN7h6Z91N' },
      { id: 'Curse of Strahd', title: 'Curse of Strahd', badge: '🏰', subtitle: undefined },
    ]);
  });

  it('falls back to the open campaign when the list has not loaded', () => {
    fixture.componentRef.setInput('userCampaigns', []);
    expect(component.campaignOptions.map((o) => o.id)).toEqual(['Test']);
  });

  it('a pick updates the name first, then asks the workspace to load it', () => {
    const events: string[] = [];
    component.campaignNameChange.subscribe((name) => events.push(`name:${name}`));
    component.campaignSelected.subscribe(() => events.push('selected'));

    component.onCampaignPicked('Curse of Strahd');
    expect(events).toEqual(['name:Curse of Strahd', 'selected']);
  });
});
