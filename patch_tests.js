const fs = require('fs');

// Fix dm.component.spec.ts
let code = fs.readFileSync('client/src/app/features/dm/dm.component.spec.ts', 'utf8');
code = code.replace(
  "char_class: 'Druid', hp_current: 24, hp_max: 24, ac: 15, stats: { WIS: 18 }",
  "char_class: 'Druid', hp_current: 24, hp_max: 24, ac: 15, stats: { WIS: 18 }, passive_perception: 14"
);
code = code.replace(
  "char_class: 'Wizard', hp_current: 12, hp_max: 12, ac: 11, stats: { WIS: 8 }",
  "char_class: 'Wizard', hp_current: 12, hp_max: 12, ac: 11, stats: { WIS: 8 }, passive_perception: 9"
);
fs.writeFileSync('client/src/app/features/dm/dm.component.spec.ts', code);

// Fix homebrew modal test
let code2 = fs.readFileSync('client/src/app/features/dm/modals/homebrew-forge-modal/homebrew-forge-modal.component.spec.ts', 'utf8');
code2 = code2.replace(
  "imports: [HomebrewForgeModalComponent]",
  "imports: [HomebrewForgeModalComponent],\n      providers: [provideHttpClient(), provideHttpClientTesting()]"
);
code2 = `import { provideHttpClient } from '@angular/common/http';\nimport { provideHttpClientTesting } from '@angular/common/http/testing';\n` + code2;
fs.writeFileSync('client/src/app/features/dm/modals/homebrew-forge-modal/homebrew-forge-modal.component.spec.ts', code2);

// Fix homebrew panel test
let code3 = fs.readFileSync('client/src/app/features/dm/panels/homebrew-panel/homebrew-panel.component.spec.ts', 'utf8');
code3 = code3.replace(
  "imports: [HomebrewPanelComponent]",
  "imports: [HomebrewPanelComponent],\n      providers: [provideHttpClient(), provideHttpClientTesting()]"
);
code3 = `import { provideHttpClient } from '@angular/common/http';\nimport { provideHttpClientTesting } from '@angular/common/http/testing';\n` + code3;
fs.writeFileSync('client/src/app/features/dm/panels/homebrew-panel/homebrew-panel.component.spec.ts', code3);
