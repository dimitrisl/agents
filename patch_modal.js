const fs = require('fs');
let code = fs.readFileSync('client/src/app/features/dm/modals/add-member-modal/add-member-modal.component.ts', 'utf8');

code = code.replace(/ForgeInputDirective,\s*/g, '');

fs.writeFileSync('client/src/app/features/dm/modals/add-member-modal/add-member-modal.component.ts', code);
