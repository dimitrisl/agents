const fs = require('fs');
let code = fs.readFileSync('client/src/app/features/dm/dm.component.ts', 'utf8');

// 1. Add encounterSyncSubject
code = code.replace(
  'private partyStateSubjects = new Map<string, Subject<void>>();',
  'private partyStateSubjects = new Map<string, Subject<void>>();\n  private encounterSyncSubject = new Subject<void>();'
);

// 2. Add subscribe in ngOnInit
code = code.replace(
  'this.loadCampaigns();',
  `this.loadCampaigns();\n\n    this.encounterSyncSubject.pipe(\n      debounceTime(500),\n      takeUntil(this.destroy$)\n    ).subscribe(() => {\n      if (!this.campaignName) return;\n      const state = {\n        round: this.round,\n        activeCombatantId: this.activeCombatantId,\n        combatants: this.combatants,\n      };\n      this.http.post(campaignUrl(this.campaignName, 'encounter'), state).subscribe({\n        error: (e) => console.error('Failed to sync encounter state', e)\n      });\n    });`
);

// 3. Update persistEncounter
code = code.replace(
  /private persistEncounter\(\) \{[\s\S]*?this\.encounterStorage\.save\(this\.campaignName, \{[\s\S]*?round: this\.round,[\s\S]*?activeCombatantId: this\.activeCombatantId,[\s\S]*?combatants: this\.combatants,[\s\S]*?\}\);\n  \}/,
  `private persistEncounter() {
    if (!this.campaignName) return;

    this.hasLiveEncounter = this.combatants.length > 0;
    if (!this.hasLiveEncounter) {
      this.encounterStorage.clear(this.campaignName);
      this.http.delete(campaignUrl(this.campaignName, 'encounter')).subscribe({
        error: (e) => console.error('Failed to clear encounter state', e)
      });
      return;
    }

    this.encounterStorage.save(this.campaignName, {
      round: this.round,
      activeCombatantId: this.activeCombatantId,
      combatants: this.combatants,
    });
    this.encounterSyncSubject.next();
  }`
);

fs.writeFileSync('client/src/app/features/dm/dm.component.ts', code);
