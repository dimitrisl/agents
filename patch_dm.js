const fs = require('fs');
let code = fs.readFileSync('client/src/app/features/dm/dm.component.ts', 'utf8');

// Replace encounterSyncSubject setup
code = code.replace(
  /this\.encounterSyncSubject\.pipe\([\s\S]*?debounceTime\(500\),[\s\S]*?takeUntil\(this\.destroy\$\)[\s\S]*?\)\.subscribe/m,
  'this.encounterSub = this.encounterSyncSubject.pipe(\n      debounceTime(500)\n    ).subscribe'
);

// Add encounterSub declaration
code = code.replace(
  'private encounterSyncSubject = new Subject<void>();',
  'private encounterSyncSubject = new Subject<void>();\n  private encounterSub?: Subscription;'
);

// Unsubscribe
code = code.replace(
  'this.openedSub?.unsubscribe();',
  'this.openedSub?.unsubscribe();\n    this.encounterSub?.unsubscribe();'
code = code.replace(
  "import { PartyMember, passivePerception } from '../../core/models/party.model';",
  "import { PartyMember } from '../../core/models/party.model';"
);

code = code.replace(
  'passive_perception: passivePerception(char.stats),',
  'passive_perception: char.passive_perception ?? 10,'
);

// Delete addPartyMember completely
code = code.replace(
  /  addPartyMember\(\) \{[\s\S]*?this\.partyMembers\.push\(member\);\n    this\.hasUnsavedPartyChanges = true;\n  \}\n/m,
  ''
);

fs.writeFileSync('client/src/app/features/dm/dm.component.ts', code);
