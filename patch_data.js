const fs = require('fs');
let code = fs.readFileSync('client/src/app/core/data/class-combat.data.ts', 'utf8');

// Remove extraCritDiceFor
code = code.replace(
  /export function extraCritDiceFor[\s\S]*?return 0;\n\}\n/m,
  ''
);

// Remove critThresholdFor
code = code.replace(
  /\/\*\* Improved Critical[\s\S]*?export function critThresholdFor[\s\S]*?return 20;\n\}\n/m,
  ''
);

fs.writeFileSync('client/src/app/core/data/class-combat.data.ts', code);
