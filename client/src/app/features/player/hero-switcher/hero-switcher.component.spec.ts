import { TestBed } from '@angular/core/testing';
import { HeroSwitcherComponent } from './hero-switcher.component';

const HEROES: any[] = [
  { char_id: 'a', char_name: 'Edrann', char_level: 11, char_class: 'Rogue', char_portrait: '/api/v1/portraits/edrann.png' },
  { char_id: 'b', char_name: 'Valeros', char_level: 5, char_class: 'Fighter', char_portrait: '/assets/anvil.png' },
];

describe('HeroSwitcherComponent', () => {
  function create(activeId = 'a', portraitUrl = '/resolved/edrann.png') {
    const fixture = TestBed.createComponent(HeroSwitcherComponent);
    fixture.componentRef.setInput('characters', HEROES);
    fixture.componentRef.setInput('activeCharacterId', activeId);
    fixture.componentRef.setInput('portraitUrl', portraitUrl);
    fixture.detectChanges();
    return fixture;
  }

  it('maps heroes onto switcher options with level and class', () => {
    const options = create().componentInstance.options;
    expect(options.map((o) => [o.id, o.title, o.subtitle])).toEqual([
      ['a', 'Edrann', 'Lvl 11 Rogue'],
      ['b', 'Valeros', 'Lvl 5 Fighter'],
    ]);
  });

  it('uses the dashboard portrait for the active hero and drops default anvil art', () => {
    const [active, other] = create().componentInstance.options;
    expect(active.imageUrl).toBe('/resolved/edrann.png');
    expect(other.imageUrl).toBeNull();
  });

  it('shows the active hero in the trigger and forwards a pick', () => {
    const fixture = create();
    const picked: string[] = [];
    fixture.componentInstance.selectCharacter.subscribe((id) => picked.push(id));

    const button = fixture.nativeElement.querySelector('button') as HTMLButtonElement;
    expect(button.textContent).toContain('Edrann');
    expect(button.getAttribute('aria-label')).toContain('Active hero: Edrann');

    const switcher = fixture.debugElement.query((d) => d.name === 'forge-switcher').componentInstance;
    switcher.valueChange.emit('b');
    expect(picked).toEqual(['b']);
  });
});
