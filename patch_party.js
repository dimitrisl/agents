const fs = require('fs');
let code = fs.readFileSync('client/src/app/core/models/party.model.ts', 'utf8');

code = code.replace(
  /export function passivePerception\([\s\S]*?\}\n/m,
  ''
);

fs.writeFileSync('client/src/app/core/models/party.model.ts', code);
