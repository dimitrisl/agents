const fs = require('fs');
let code = fs.readFileSync('client/src/app/features/dm/dm.component.ts', 'utf8');

code = code.replace(
  'passive_perception: passivePerception(stats),',
  'passive_perception: 10,'
);

fs.writeFileSync('client/src/app/features/dm/dm.component.ts', code);
