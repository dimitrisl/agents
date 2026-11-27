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

  it('filters out monsters, spells, feats, and features from availableHomebrewItems', () => {
    component.homebrewItems = [
      { _id: 'hb_1', name: 'Flame Tongue', homebrew_type: 'weapon' },
      { _id: 'hb_2', name: 'Goblin Boss', homebrew_type: 'monster' },
      { _id: 'hb_3', name: 'Bag of Holding', homebrew_type: 'item' },
      { _id: 'hb_4', name: 'Solar Flare', homebrew_type: 'spell' },
      { _id: 'hb_5', name: 'Shadow Touched', homebrew_type: 'feat' },
    ];

    expect(component.availableHomebrewItems.map((h) => h.name)).toEqual([
      'Flame Tongue',
      'Bag of Holding',
    ]);
  });

  it('excludes stale character IDs not in partyMembers and resets selection on closeModal', () => {
    component.selectedCharIds = {
      char_1: true,
      removed_char: true,
    };

    expect(component.getSelectedIds()).toEqual(['char_1']);

    component.splitCurrency = true;
    component.reason = 'Dragon Hoard';
    component.closeModal();

    expect(component.selectedCharIds).toEqual({});
    expect(component.splitCurrency).toBe(false);
    expect(component.reason).toBe('Quest Reward');
  });

  it('ignores unlinked custom party members in allSelected/toggleRecipient and computes live split preview', () => {
    component.partyMembers = [
      ...mockParty,
      {
        name: 'Camp Mascot NPC',
        char_class: 'Commoner',
        level: 1,
        hp_current: 4,
        hp_max: 4,
        ac: 10,
        passive_perception: 10,
        conditions: [],
      },
    ];

    expect(component.targetableMembers.length).toBe(2);
    expect(component.unlinkedMembers.length).toBe(1);

    component.toggleRecipient('');
    expect(component.getSelectedIds()).toEqual([]);

    component.toggleSelectAll(true);
    expect(component.allSelected).toBe(true);
    expect(component.getSelectedIds()).toEqual(['char_1', 'char_2']);

    component.onCoinInput('gp', '1');
    component.splitCurrency = true;
    expect(component.splitPreviewText).toBe('Each hero gets 5 sp');

    // Negative values are clamped safely instead of sending negative currency
    component.gp = -50;
    component.sp = 10;
    expect(component.hasPositiveCurrency).toBe(true);
  });

  it('lazily requests official SRD catalog items, sends structured item + quantity, and formats 422 array errors', () => {
    const toastSpy = jest.spyOn(toast, 'showMessage');
    let requested = 0;
    component.requestOfficialItems.subscribe(() => {
      requested += 1;
    });

    component.setItemSource('official');
    expect(requested).toBe(1);

    component.officialItems = [
      {
        name: 'Potion of Healing',
        type: 'Potion',
        weight: 0.5,
        description: 'Regain 2d4 + 2 HP.',
      },
      {
        name: 'Plate Armor',
        type: 'Heavy Armor',
        weight: 65,
        description: 'Heavy interlocking plates.',
      },
    ];
    component.officialItemSearch = 'potion';
    expect(component.filteredOfficialItems.map((i) => i.name)).toEqual(['Potion of Healing']);

    component.selectedCharIds = { char_1: true };
    component.selectedOfficialItemName = 'Potion of Healing';
    component.onQuantityInput('3', 'official');
    component.distribute();

    const req = http.expectOne((r) => r.url.endsWith('/campaigns/Phandelver/loot/distribute'));
    expect(req.request.body.items).toEqual([
      {
        name: 'Potion of Healing',
        description: 'Regain 2d4 + 2 HP.',
        type: 'item',
        quantity: 3,
        weight: 0.5,
      },
    ]);

    // Simulate FastAPI 422 validation error array -> formatted cleanly without [object Object]
    req.flush(
      { detail: [{ loc: ['body', 'currency', 'gp'], msg: 'Input should be >= 0' }] },
      { status: 422, statusText: 'Unprocessable Entity' }
    );
    expect(toastSpy).toHaveBeenCalledWith('❌ DISTRIBUTION FAILED', 'Input should be >= 0');
  });

  it('omits ac_bonus on official Shield +2, syncs DOM input values on invalid chars, clears non-matching search selection, and enforces mutually exclusive tabs', () => {
    // 1. DOM input sanitization rewrites <input>.value immediately when invalid characters are typed
    const coinInput = document.createElement('input');
    coinInput.value = '-abc';
    component.onCoinInput('gp', { target: coinInput } as unknown as Event);
    expect(component.gp).toBe(0);
    expect(coinInput.value).toBe('');

    coinInput.value = '50a';
    component.onCoinInput('gp', { target: coinInput } as unknown as Event);
    expect(component.gp).toBe(50);
    expect(coinInput.value).toBe('50');

    const qtyInput = document.createElement('input');
    // Backspace clears display to '' (no snap-back to '1' that causes '13' on next digit!)
    qtyInput.value = '';
    component.onQuantityInput({ target: qtyInput } as unknown as Event, 'official');
    expect(component.officialItemQuantity).toBe(1);
    expect(component.officialItemQuantityInput).toBe('');
    expect(qtyInput.value).toBe('');

    // Typing '3' after Backspace sets quantity cleanly to 3
    qtyInput.value = '3';
    component.onQuantityInput({ target: qtyInput } as unknown as Event, 'official');
    expect(component.officialItemQuantity).toBe(3);
    expect(component.officialItemQuantityInput).toBe('3');
    expect(qtyInput.value).toBe('3');

    // Invalid chars/zero strip cleanly and blur restores '1'
    qtyInput.value = '0abc';
    component.onQuantityInput({ target: qtyInput } as unknown as Event, 'official');
    expect(component.officialItemQuantity).toBe(1);
    expect(qtyInput.value).toBe('');
    component.onQuantityBlur('official');
    expect(component.officialItemQuantityInput).toBe('1');

    // getSelectedIds() follows visible partyMembers order, not click order
    component.toggleRecipient('char_2');
    component.toggleRecipient('char_1');
    expect(component.getSelectedIds()).toEqual(['char_1', 'char_2']);
    component.selectedCharIds = {};

    // In-flight distribute finishing after modal close + reopen does not close the new session
    fixture.componentRef.setInput('open', true);
    fixture.detectChanges();
    component.selectedCharIds = { char_1: true };
    component.gp = 10;
    component.distribute();
    const inFlightReq = http.expectOne((r) => r.url.endsWith('/campaigns/Phandelver/loot/distribute'));

    // Close and reopen before response arrives
    component.closeModal();
    fixture.componentRef.setInput('open', false);
    fixture.detectChanges();
    fixture.componentRef.setInput('open', true);
    fixture.detectChanges();
    expect(component.isDistributing).toBe(false);

    let closedNewSession = false;
    component.closed.subscribe(() => {
      closedNewSession = true;
    });
    inFlightReq.flush({ success: true, message: 'ok' });
    expect(closedNewSession).toBe(false);

    // 2. Switching itemSource clears hidden tabs (true radiogroup semantics)
    component.customItemName = 'Old Rope';
    component.setItemSource('official');
    expect(component.customItemName).toBe('');

    // 3. Filtering Official SRD clears selectedOfficialItemName if it no longer matches
    component.officialItems = [
      { name: 'Shield +2', type: 'Shield', weight: 6, ac_bonus: 2, magic_bonus: 2, description: 'Magic shield.' },
      { name: 'Potion of Healing', type: 'Potion', weight: 0.5, description: 'Heals.' },
    ];
    component.selectedOfficialItemName = 'Shield +2';
    component.onOfficialSearchChange('potion');
    expect(component.selectedOfficialItemName).toBe('');

    // 4. Official Shield +2 payload omits ac_bonus so backend resolves +2 base +2 magic = +4 AC
    component.onOfficialSearchChange('');
    component.selectedOfficialItemName = 'Shield +2';
    component.selectedCharIds = { char_1: true };
    component.distribute();
    const req = http.expectOne((r) => r.url.endsWith('/campaigns/Phandelver/loot/distribute'));
    expect(req.request.body.items).toEqual([
      {
        name: 'Shield +2',
        description: 'Magic shield.',
        type: 'item',
        weight: 6,
      },
    ]);
    expect('ac_bonus' in req.request.body.items[0]).toBe(false);
    req.flush({ success: true, message: 'ok' });
  });
});
