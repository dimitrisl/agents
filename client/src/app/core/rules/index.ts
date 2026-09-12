/**
 * The rules the sheet computes, as plain functions.
 *
 * Nothing in this folder imports from `@angular/*` — no signals, no injection, no
 * DOM. It is the arithmetic a player sees and has to be able to trust: ability
 * modifiers, skill bonuses, rests, spell slots, HP and level-ups. Import from
 * this barrel, never from the individual files.
 */
export * from './ability';
export * from './hit-points';
export * from './level-up';
export * from './rest';
export * from './skills';
export * from './spell-slots';
