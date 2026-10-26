import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { LootDistributeModalComponent } from './loot-distribute-modal.component';
import { RollToastService } from '../../../../core/services/roll-toast.service';
import { PartyMember } from '../../../../core/models/party.model';

describe('LootDistributeModalComponent', () => {
  let component: LootDistributeModalComponent;
  let fixture: ComponentFixture<LootDistributeModalComponent>;
  let http: HttpTestingController;
  let toast: RollToastService;

  const mockParty: PartyMember[] = [
    {
      char_id: 'char_1',
      name: 'Throg',
      char_class: 'Barbarian',
      level: 3,
      hp_current: 35,
      hp_max: 35,
      ac: 14,
      conditions: [],
    },
    {
      char_id: 'char_2',
      name: 'Elrond',
      char_class: 'Wizard',
      level: 3,
      hp_current: 18,
      hp_max: 18,
      ac: 12,
      conditions: [],
    },
  ];

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [LootDistributeModalComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        RollToastService,
      ],
    }).compileComponents();

    http = TestBed.inject(HttpTestingController);
    toast = TestBed.inject(RollToastService);
    fixture = TestBed.createComponent(LootDistributeModalComponent);
    component = fixture.componentInstance;
    component.campaignName = 'Phandelver';
    component.partyMembers = mockParty;
  });

  afterEach(() => {
    http.verify();
  });

  it('selects and deselects all recipients', () => {
    expect(component.allSelected).toBe(false);

    component.toggleSelectAll(true);
    expect(component.allSelected).toBe(true);
    expect(component.getSelectedIds()).toEqual(['char_1', 'char_2']);

    component.toggleSelectAll(false);
    expect(component.allSelected).toBe(false);
    expect(component.getSelectedIds()).toEqual([]);
  });

  it('warns when distributing with no recipients', () => {
    jest.spyOn(toast, 'showMessage');
    component.gp = 100;
    component.distribute();

    expect(toast.showMessage).toHaveBeenCalledWith(
      '⚠️ NO RECIPIENTS',
      expect.stringContaining('Select at least one')
    );
  });

  it('warns when distributing with no loot specified', () => {
    jest.spyOn(toast, 'showMessage');
    component.selectedCharIds = { char_1: true };
    component.distribute();

    expect(toast.showMessage).toHaveBeenCalledWith(
      '⚠️ NO LOOT',
      expect.stringContaining('Specify currency or an item')
    );
  });

  it('distributes currency and custom item successfully', () => {
    jest.spyOn(toast, 'showMessage');
    let distributedEmitted = false;
    component.distributed.subscribe(() => {
      distributedEmitted = true;
    });

    component.selectedCharIds = { char_1: true, char_2: true };
    component.gp = 50;
    component.pp = 2;
    component.splitCurrency = true;
    component.customItemName = 'Ruby of the War Mage';
    component.customItemDesc = 'Common wondrous item';
    component.reason = 'Chest in goblin cave';

    component.distribute();

    const req = http.expectOne((r) => r.url.endsWith('/campaigns/Phandelver/loot/distribute'));
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({
      character_ids: ['char_1', 'char_2'],
      split_currency: true,
      reason: 'Chest in goblin cave',
      currency: { pp: 2, gp: 50, ep: 0, sp: 0, cp: 0 },
      items: [{
        name: 'Ruby of the War Mage',
        description: 'Common wondrous item',
        type: 'item',
      }],
    });

    req.flush({
      success: true,
      message: 'Loot distributed to 2 character(s).',
      currency_awarded: { pp: 1, gp: 25, ep: 0, sp: 0, cp: 0 },
      items_awarded: ['Ruby of the War Mage'],
    });

    expect(toast.showMessage).toHaveBeenCalledWith(
      '💰 LOOT DISTRIBUTED',
      expect.stringContaining('Loot distributed')
    );
    expect(distributedEmitted).toBe(true);
  });

  it('filters out monsters from availableHomebrewItems', () => {
    component.homebrewItems = [
      { _id: 'hb_1', name: 'Flame Tongue', homebrew_type: 'weapon' },
      { _id: 'hb_2', name: 'Goblin Boss', homebrew_type: 'monster' },
      { _id: 'hb_3', name: 'Bag of Holding', homebrew_type: 'item' },
    ];

    expect(component.availableHomebrewItems.map((h) => h.name)).toEqual([
      'Flame Tongue',
      'Bag of Holding',
    ]);
  });
});
