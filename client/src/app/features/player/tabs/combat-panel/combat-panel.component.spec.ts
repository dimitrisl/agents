import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { CombatPanelComponent } from './combat-panel.component';
import { CharacterSchema } from '../../../../core/models/character.model';
import { DiceService } from '../../../../core/services/dice.service';
import { RollToastService } from '../../../../core/services/roll-toast.service';
import { ClassCombatService } from '../../../../core/services/class-combat.service';

describe('CombatPanelComponent', () => {
  let component: CombatPanelComponent;
  let fixture: ComponentFixture<CombatPanelComponent>;
  let toast: RollToastService;

  const mockChar: CharacterSchema = {
    char_id: 'test-char',
    char_name: 'Thorin',
    char_class: 'Fighter',
    char_level: 5,
    race: 'Dwarf',
    background: 'Soldier',
    armor_class: 18,
    hp_max: 45,
    proficiency_bonus: 3,
    speed: 25,
    stats: { STR: 18, DEX: 10, CON: 16, INT: 10, WIS: 12, CHA: 8 },
    currency: { cp: 10, sp: 50, ep: 0, gp: 120, pp: 1 },
    equipment: [
      { name: 'Potion of Healing', quantity: 2, equipped: false },
      { name: 'Cloak of Protection', equipped: true, attuned: true },
      { name: 'Ring of Warmth', equipped: true, attuned: true },
    ],
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CombatPanelComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        DiceService,
        RollToastService,
        ClassCombatService,
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(CombatPanelComponent);
    component = fixture.componentInstance;
    component.char = JSON.parse(JSON.stringify(mockChar));
    toast = TestBed.inject(RollToastService);
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
    expect(component.currency.gp).toBe(120);
  });

  it('should add coins and spend coins correctly', () => {
    const saveSpy = jest.spyOn(component.save, 'emit');
    component.openCoinModal('gp');
    expect(component.showCoinModal).toBe(true);

    component.addCoinPill(50);
    component.executeAddCoins();
    expect(component.currency.gp).toBe(170);
    expect(saveSpy).toHaveBeenCalled();
    expect(component.showCoinModal).toBe(false);

    component.openCoinModal('gp');
    component.addCoinPill(30);
    component.executeSpendCoins();
    expect(component.currency.gp).toBe(140);
  });

  it('should block spending more coins than available', () => {
    const toastSpy = jest.spyOn(toast, 'showMessage');
    component.openCoinModal('gp');
    component.addCoinPill(999);
    component.executeSpendCoins();

    expect(toastSpy).toHaveBeenCalledWith('⚠️ INSUFFICIENT COINS', expect.any(String));
    expect(component.currency.gp).toBe(120);
  });

  it('should enforce 3-item attunement limit', () => {
    const toastSpy = jest.spyOn(toast, 'showMessage');
    const saveSpy = jest.spyOn(component.save, 'emit');

    expect(component.attunedCount).toBe(2);

    // Add a 3rd attuned item
    const item3 = { name: 'Boots of Speed', attuned: false };
    component.char.equipment?.push(item3);
    component.toggleAttuned(item3);
    expect(item3.attuned).toBe(true);
    expect(component.attunedCount).toBe(3);
    expect(saveSpy).toHaveBeenCalled();

    // Attempt to add a 4th attuned item
    const item4 = { name: 'Amulet of Health', attuned: false };
    component.char.equipment?.push(item4);
    component.toggleAttuned(item4);
    expect(item4.attuned).toBe(false);
    expect(toastSpy).toHaveBeenCalledWith('🔮 ATTUNEMENT LIMIT', expect.any(String));
  });

  it('should detect healing potions and emit consumePotion', () => {
    const consumeSpy = jest.spyOn(component.consumePotion, 'emit');
    const potionItem = component.char.equipment![0];

    expect(component.isHealingPotion(potionItem)).toBe(true);
    component.drinkPotion(potionItem, new MouseEvent('click'));

    expect(consumeSpy).toHaveBeenCalledWith({
      item: potionItem,
      dice: '2d4',
      bonus: 2,
      name: 'Potion of Healing',
    });
  });

  it('should adjust quantity on item', () => {
    const saveSpy = jest.spyOn(component.save, 'emit');
    const item = component.char.equipment![0];
    expect(item.quantity).toBe(2);

    component.adjustQuantity(item, 1, new MouseEvent('click'));
    expect(item.quantity).toBe(3);
    expect(saveSpy).toHaveBeenCalled();

    component.adjustQuantity(item, -2, new MouseEvent('click'));
    expect(item.quantity).toBe(1);
  });
});
