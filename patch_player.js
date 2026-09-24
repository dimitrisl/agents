const fs = require('fs');
let code = fs.readFileSync('client/src/app/features/player/player.component.ts', 'utf8');

// 1. Add encounterState property
code = code.replace(
  '  rollMode: RollMode = \'normal\';',
  '  rollMode: RollMode = \'normal\';\n  encounterState: any = null;'
);

// 2. Add encounterState fetch inside loadCampaignMessages
code = code.replace(
  '  private loadCampaignMessages(campaignName: string, isCatchUp: boolean): void {',
  `  private loadCampaignMessages(campaignName: string, isCatchUp: boolean): void {
    this.http.get<any>(campaignUrl(campaignName, 'encounter')).subscribe({
      next: (enc) => {
        this.encounterState = enc;
        this.cdr.markForCheck();
      },
      error: () => {
        this.encounterState = null;
        this.cdr.markForCheck();
      }
    });
`
);

// 3. Add encounter_update listener in messages$
code = code.replace(
  /\} else if \(msg\.type === 'party_update'\) \{/,
  `} else if (msg.type === 'encounter_update') {
        this.encounterState = msg['payload'];
        this.cdr.markForCheck();
      } else if (msg.type === 'party_update') {`
);

fs.writeFileSync('client/src/app/features/player/player.component.ts', code);
