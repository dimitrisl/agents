const fs = require('fs');
let code = fs.readFileSync('client/src/app/features/dm/dm.component.ts', 'utf8');

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
