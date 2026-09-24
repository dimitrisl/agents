const fs = require('fs');
let code = fs.readFileSync('client/src/app/core/services/class-combat.service.ts', 'utf8');

code = code.replace(
  'const tier = cantripTierFor(ctx.level);',
  'const tier = ctx.level >= 17 ? 4 : ctx.level >= 11 ? 3 : ctx.level >= 5 ? 2 : 1;'
);

fs.writeFileSync('client/src/app/core/services/class-combat.service.ts', code);
