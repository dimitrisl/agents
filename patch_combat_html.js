const fs = require('fs');
let code = fs.readFileSync('client/src/app/features/player/tabs/combat-panel/combat-panel.component.html', 'utf8');

const trackerHtml = `
  <!-- INITIATIVE TRACKER -->
  <div
    *ngIf="encounterState && encounterState.combatants?.length > 0"
    class="rounded-xl border border-hairline bg-black/40 p-4 shadow-sm"
  >
    <div class="flex items-center justify-between mb-3 border-b border-hairline pb-2">
      <h3 class="font-display text-title text-ink uppercase tracking-wider">
        ⚔️ Initiative Tracker <span class="text-label text-muted ml-2">Round {{ encounterState.round || 1 }}</span>
      </h3>
    </div>

    <div class="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
      <div
        *ngFor="let combatant of encounterState.combatants"
        class="flex-shrink-0 flex flex-col items-center justify-center p-3 rounded-lg border min-w-[110px]"
        [ngClass]="{
          'border-gold bg-gold/10 text-gold shadow-[0_0_10px_rgba(255,215,0,0.2)]': encounterState.activeCombatantId === combatant.id,
          'border-hairline bg-black/20 text-muted': encounterState.activeCombatantId !== combatant.id,
          'opacity-50 grayscale': combatant.hp <= 0
        }"
      >
        <div class="text-[1.5rem] mb-1 font-black font-display">{{ combatant.initiative }}</div>
        <div class="text-label font-bold text-center truncate w-full px-1" [class.text-ink]="encounterState.activeCombatantId !== combatant.id" [title]="combatant.name">
          {{ combatant.name }}
        </div>
        <div *ngIf="combatant.is_player" class="text-micro uppercase mt-1 tracking-widest" [class.text-gold]="encounterState.activeCombatantId === combatant.id" [class.text-ink]="encounterState.activeCombatantId !== combatant.id">Hero</div>
        <div *ngIf="combatant.hp <= 0" class="text-micro text-red-500 font-bold uppercase mt-1 tracking-widest">Down</div>
      </div>
    </div>
  </div>
`;

code = code.replace(
  '<div class="flex flex-col gap-6">',
  '<div class="flex flex-col gap-6">\n' + trackerHtml
);

fs.writeFileSync('client/src/app/features/player/tabs/combat-panel/combat-panel.component.html', code);
