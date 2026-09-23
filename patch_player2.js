const fs = require('fs');
let code = fs.readFileSync('client/src/app/features/player/player.component.ts', 'utf8');

code = code.replace(/this\.cdr\.markForCheck\(\);/g, '');

fs.writeFileSync('client/src/app/features/player/player.component.ts', code);
