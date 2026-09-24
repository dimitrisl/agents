const fs = require('fs');
let code = fs.readFileSync('client/src/app/core/services/class-combat.service.ts', 'utf8');

// Remove extraCritDiceFor, critThresholdFor from imports
code = code.replace(
  /  critThresholdFor,\n  extraCritDiceFor,\n/m,
  ''
);

// Remove cantripTierFor definition
code = code.replace(
  /export function cantripTierFor\(level: number\): number \{ return level >= 17 \? 4 : level >= 11 \? 3 : level >= 5 \? 2 : 1; \}\n/m,
  ''
);

// Update getProfile method to use the API response directly and not fallback to calculating the profile fields if possible
const newGetProfile = `  getProfile(char: CharacterSchema): Observable<CombatProfile> {
    const ctx = this.buildContext(char);

    // Default cantrip tier for fallbacks
    const defaultCantripTier = ctx.level >= 17 ? 4 : ctx.level >= 11 ? 3 : ctx.level >= 5 ? 2 : 1;

    if (!ctx.charClass) {
        return of({
            actions: this.universalActions(char, ctx),
            extraCritDice: 0,
            critThreshold: 20,
            cantripTier: defaultCantripTier,
        });
    }

    const edParam = ctx.is2024 ? '2024 Edition' : '2014 Edition';
    let url = \`\${environment.apiBaseUrl}/rules/classes/\${ctx.charClass.toLowerCase()}/scaling?level=\${ctx.level}&edition=\${encodeURIComponent(edParam)}\`;
    if (ctx.subclass) {
        url += \`&subclass=\${encodeURIComponent(ctx.subclass)}\`;
    }

    return this.http.get<any>(url).pipe(
      map(res => {
        const apiActions = res.actions || [];
        const mappedActions = apiActions.map((a: any) => ({
          ...a,
          icon: a.icon || '⚔️',
          source: a.source || \`\${ctx.charClass} \${ctx.level}\`
        }));

        return {
          actions: [...mappedActions, ...this.universalActions(char, ctx)],
          extraCritDice: res.extraCritDice || 0,
          critThreshold: res.critThreshold || 20,
          cantripTier: res.cantripTier || defaultCantripTier,
        }
      }),
      catchError(() => {
        return of({
          actions: this.universalActions(char, ctx),
          extraCritDice: 0,
          critThreshold: 20,
          cantripTier: defaultCantripTier,
        });
      })
    );
  }`;

// Replace the existing getProfile
code = code.replace(
  /  getProfile\(char: CharacterSchema\): Observable<CombatProfile> \{[\s\S]*?    \);\n  \}/m,
  newGetProfile
);

fs.writeFileSync('client/src/app/core/services/class-combat.service.ts', code);
