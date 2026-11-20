import { Component, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeIconComponent,
  ForgeEmptyStateComponent,
  ForgeInputDirective,
  ForgePageComponent,
} from '../../shared/ui';

export interface FaqItem {
  id: string;
  category: 'dm' | 'player' | 'companion' | 'forge' | 'vtt' | 'rules' | 'admin';
  categoryLabel: string;
  badgeTone: 'accent' | 'success' | 'gold' | 'danger' | 'muted';
  question: string;
  answerHtml: string;
  tags: string[];
}

@Component({
  selector: 'app-faq',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterLink,
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeIconComponent,
    ForgeEmptyStateComponent,
    ForgeInputDirective,
    ForgePageComponent,
  ],
  templateUrl: './faq.component.html',
  styleUrl: './faq.component.css',
})
export class FaqComponent {
  searchQuery = signal<string>('');
  selectedCategory = signal<string>('dm');
  openQuestions = signal<Set<string>>(
    // First question of each axis starts open; the rest are one click away.
    new Set([
      'dm-1',
      'player-1',
      'companion-1',
      'forge-1',
      'vtt-1',
      'rules-1',
      'admin-1',
    ])
  );

  readonly categories = [
    { id: 'dm', label: '🏰 Dungeon Master (DM)', icon: '🏰' },
    { id: 'player', label: '🗡️ Player', icon: '🗡️' },
    { id: 'companion', label: '📱 Mobile Companion', icon: '📱' },
    { id: 'forge', label: '✦ Character Forge & Imports', icon: '✦' },
    { id: 'vtt', label: '🗺️ VTT & Homebrew', icon: '🗺️' },
    { id: 'rules', label: '📚 Rules & AI Arbiter', icon: '📚' },
    { id: 'admin', label: '🛡️ Admin & Security', icon: '🛡️' },
  ];

  readonly faqItems: FaqItem[] = [
    // ==========================================
    // 1. DUNGEON MASTER CAPABILITIES
    // ==========================================
    {
      id: 'dm-1',
      category: 'dm',
      categoryLabel: 'Dungeon Master (DM)',
      badgeTone: 'gold',
      question:
        'How are the DM Workspace, Campaign management, Invite Codes, and Sticky Session Board organized?',
      answerHtml: `
        <p>The <strong>DM Workspace (<code>/dm</code>)</strong> is the Dungeon Master's command center (designed for Desktop/Laptop displays <code>&ge; 1024px</code>) and includes:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>🏰 Campaign Header &amp; Switcher:</strong> Quickly pick an active campaign from the dropdown, create a new campaign (with title, initial notes, and <strong>2014 Edition</strong> or <strong>2024 Revision</strong> ruleset), or delete a campaign.</li>
          <li><strong>🔑 6-Character Invite Code:</strong> Generate or rotate a unique invite code in one click so players can link their characters to the table via <em>Join Campaign</em>.</li>
          <li><strong>📊 Sticky Session Board (Left Column):</strong> Persistent live control panel showing:
            <ul class="list-disc list-inside ml-5 mt-1 space-y-0.5 text-sm">
              <li>Live counters for <strong>Party Size</strong>, <strong>Average Level</strong>, <strong>In Combat</strong>, and <strong>Current Turn / Round</strong>.</li>
              <li><strong>Party Health Mini-Bars:</strong> Real-time health bars (<code>hp_current / hp_max</code>) and portraits for every party member.</li>
              <li><strong>🗺️ Open VTT Grid:</strong> Opens the 2D Virtual Tabletop simultaneously on the DM's screen and all connected players' views over WebSockets (<code>vtt_toggle</code>).</li>
            </ul>
          </li>
        </ul>
      `,
      tags: ['dm', 'campaign', 'invite code', 'session board', 'vtt toggle', 'edition'],
    },
    {
      id: 'dm-2',
      category: 'dm',
      categoryLabel: 'Dungeon Master (DM)',
      badgeTone: 'gold',
      question:
        'What does the Live Party Tracker (👥 Party Tab) give the DM during play?',
      answerHtml: `
        <p>The <strong>👥 Live Party Tracker</strong> tab gives the DM full visibility and control over party heroes:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>🟢 Live WebSocket Presence:</strong> Shows <code>🟢 Online</code> or <code>⚪ Offline</code> next to each player's hero and username.</li>
          <li><strong>❤️ Real-Time HP Steppers &amp; Direct Input:</strong> Adjust HP with <code>− / +</code> buttons or type a value directly. Changes are debounced (400ms), saved atomically, and pushed to the player's sheet instantaneously via WebSockets!</li>
          <li><strong>🛡️ AC Breakdown &amp; 👁️ Passive Perception:</strong> Instant display of Armor Class (with formula tooltip) and Passive Perception for every hero for behind-the-screen checks.</li>
          <li><strong>🎲 DM Quick Check (Secret DM Rolls):</strong> Six buttons (<code>STR, DEX, CON, INT, WIS, CHA</code>) on each hero card let the DM roll a secret Ability Check using the hero's real sheet modifier behind the DM screen!</li>
          <li><strong>🩸 14 Conditions Management:</strong> Toggle conditions (<em>Poisoned, Concentrating, Stunned, Unconscious, Blinded, Charmed, Frightened, Grappled, Incapacitated, Invisible, Paralyzed, Petrified, Prone, Restrained</em>) with two-way sync.</li>
          <li><strong>➕ Add Member Modal (2 Ways to Add):</strong> Add a member either by selecting an existing hero from the Vault (<em>Select Player Hero from Vault</em>) or by sharing the 6-character <em>Invite Code</em> with players.</li>
        </ul>
      `,
      tags: ['dm', 'party tracker', 'online', 'hp', 'quick check', 'conditions', 'passive perception'],
    },
    {
      id: 'dm-3',
      category: 'dm',
      categoryLabel: 'Dungeon Master (DM)',
      badgeTone: 'gold',
      question:
        'How do the Initiative Combat Tracker (⚔️ Initiative Tab), Timed Conditions, and Death Saves work?',
      answerHtml: `
        <p>The <strong>⚔️ Initiative Tracker</strong> tab is built for fast, accurate combat resolution:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>👥 Import Party &amp; ➕ Add Monster:</strong> Pull all party heroes in with one click (carrying their live HP/AC) and quickly add monsters or NPCs from the Bestiary or custom entries.</li>
          <li><strong>🎲 Roll All Initiative:</strong> Automatically rolls Initiative for all combatants with automatic <strong>DEX tie-breaking</strong> and turn-order sorting.</li>
          <li><strong>➡️ Next / Previous Turn &amp; Mobile Alerts:</strong> Advancing turns increments rounds, persists combat state to both backend and local storage, and triggers vibration/banner alerts (<em>It's Your Turn!</em> / <em>On Deck</em>) on players' phones!</li>
          <li><strong>⏳ Timed Conditions with Auto-Expiry:</strong> Apply any Condition with a <strong>Duration in rounds</strong> (e.g., 3 rounds). Remaining rounds tick down automatically each round and clear once expired!</li>
          <li><strong>💀 Death Saves Tracker:</strong> When a hero drops to <code>0 HP</code>, <em>Successes (1–3)</em> and <em>Failures (1–3)</em> trackers appear with automatic <strong>💚 Stable</strong> or <strong>💀 Dead</strong> states.</li>
          <li><strong>⚠️ Monster Danger Indicator &amp; 📜 Statblock Modal:</strong> Automatic threat rating (<em>Low, Moderate, High, Deadly</em>) plus a <strong>📜 Statblock</strong> modal showing full stats, traits, and 1-click attack/damage rolls.</li>
        </ul>
      `,
      tags: ['dm', 'initiative', 'combat', 'timed conditions', 'death saves', 'statblock', 'turn order'],
    },
    {
      id: 'dm-4',
      category: 'dm',
      categoryLabel: 'Dungeon Master (DM)',
      badgeTone: 'gold',
      question:
        'How do Roll Requests, Secret Rolls, and the Table Inbox (💬 Whispers) work?',
      answerHtml: `
        <p>DM-to-player dice prompts and messages run in real time over WebSockets:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>🎲 Request a Roll Modal:</strong> Choose a player, roll type (<em>Ability Check, Skill Check, Saving Throw, Attack Roll, Initiative</em>), stat/skill (e.g., <em>Perception</em> or <em>DEX</em>), and reason (e.g., <em>Dragon Breath Fire Save</em>). An interactive 60-second prompt opens immediately on the player's screen!</li>
          <li><strong>🔒 Secret Roll Flag &amp; Behind-the-Screen Rolls:</strong> Either flag a prompt as a <em>Secret Roll</em> or roll silently yourself from the Party Panel (<em>DM Quick Check</em>) without exposing anything to the player UI.</li>
          <li><strong>💬 Send Whisper &amp; Broadcast:</strong> Send private whispers to a specific hero or broadcast announcements to the entire table (<code>All Players</code>).</li>
          <li><strong>📥 Table Inbox Drawer:</strong> Unified history drawer at the bottom of the DM Workspace with an unread badge. Shows all Whispers, Roll Request statuses (<code>Pending</code>, <code>Resolved</code> with total, dice expression, Advantage/Disadvantage, and Situational Bonus, or <code>Missed</code>), quick replies, and a <strong>🚩 Report</strong> moderation control.</li>
        </ul>
      `,
      tags: ['dm', 'roll request', 'secret roll', 'whisper', 'table inbox', 'moderation'],
    },
    {
      id: 'dm-5',
      category: 'dm',
      categoryLabel: 'Dungeon Master (DM)',
      badgeTone: 'gold',
      question:
        'How do the World Lore Database (📚 Entities Tab), Paste & Go AI Extractor, and Campaign Notes work?',
      answerHtml: `
        <p>The DM has a complete campaign world-building archive:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>📚 World Lore Database (6 Entity Types):</strong> Create, edit, and organize <code>Lore Note</code>, <code>NPC</code>, <code>Villain</code>, <code>Faction</code>, <code>Location</code>, and <code>Monster</code> entries.</li>
          <li><strong>📍 Location Links &amp; Artwork:</strong> Link NPCs or Monsters to a campaign <code>Location</code> and attach portraits or maps (Asset Image Upload) plus Markdown notes.</li>
          <li><strong>✨ Paste &amp; Go AI Entity Extractor:</strong> Paste raw notes, adventure snippets, or improvised lore and let AI extract structured entities along with their <strong>Extracted Stats</strong> straight into the campaign database!</li>
          <li><strong>📝 Campaign Notes Tab:</strong> Dedicated scratchpad for quick DM session notes with instant persistence per campaign.</li>
        </ul>
      `,
      tags: ['dm', 'world lore', 'entities', 'paste and go', 'npc', 'locations', 'notes'],
    },
    {
      id: 'dm-6',
      category: 'dm',
      categoryLabel: 'Dungeon Master (DM)',
      badgeTone: 'gold',
      question:
        'How do the DM AI Generators (🎲 Encounter Generator, Quick NPC Forge & Riddles) work?',
      answerHtml: `
        <p>In the <strong>🎲 AI Generators</strong> tab, the DM can generate rules-aware content in seconds tailored to the campaign's edition (2014 or 2024):</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>⚔️ Random Encounter Generator:</strong> Reads active <code>partySize</code> and <code>avgLevel</code> automatically. Pick Difficulty (<em>Easy, Medium, Hard, Deadly</em>) and Environment (e.g., <em>Dungeon, Underdark, Forest</em>) to generate an encounter hook and monster roster with HP/AC. Click <strong>➕ Add to Initiative</strong> to drop all foes straight into the tracker!</li>
          <li><strong>👤 Quick NPC Forge:</strong> Enter a short concept (e.g., <em>Greedy merchant thief</em>) and AI generates a ready-to-play NPC with appearance, motivation, secret, and roleplay cues.</li>
          <li><strong>🧩 AI Riddle Generator:</strong> Generates thematic puzzles, traps, and hints for dungeons.</li>
        </ul>
      `,
      tags: ['dm', 'ai generators', 'encounter generator', 'npc forge', 'riddles'],
    },
    {
      id: 'dm-7',
      category: 'dm',
      categoryLabel: 'Dungeon Master (DM)',
      badgeTone: 'gold',
      question:
        'What is included in Session Prep (📜 Campaign Skeleton, Session Forge, Audio Chronicle & Journey Graph)?',
      answerHtml: `
        <p>The <strong>📜 Session Prep</strong> tab bundles 4 planning and journaling tools:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>🏛️ The Campaign Skeleton (Plot Architect):</strong> Define <em>Core Concept</em>, <em>Tone &amp; Setting</em>, <em>Key Milestones</em>, <em>Plot Twists</em>, and <em>Max Sessions</em>. Click <strong>Generate Session Outlines</strong> to draft a full session-by-session arc with Main Events, Locations, NPCs, and Hooks!</li>
          <li><strong>⚔️ The Session Forge (Lazy DM Prep Architect):</strong> Combines DM ideas with prior sessions and World Lore to produce a <strong>🔥 Strong Start</strong>, <strong>🤫 5 Secrets &amp; Clues</strong>, <strong>⚔️ Potential Encounters</strong>, and <strong>🗣️ Key NPCs</strong>.</li>
          <li><strong>🎙️ The Campaign Chronicle (Audio &amp; Text Journaling):</strong> Upload session audio (MP3/WAV up to 100MB, magic-byte validated) or paste session notes. AI transcribes, produces a detailed <strong>Session Summary</strong>, and pulls out newly introduced <em>Extracted Entities</em>!</li>
          <li><strong>🗺️ Party Journey Graph:</strong> Interactive visual timeline mapping all logged sessions and tracing the locations your party visited from Session 1 onward.</li>
        </ul>
      `,
      tags: ['dm', 'session prep', 'campaign skeleton', 'session forge', 'audio', 'journey graph'],
    },

    // ==========================================
    // 2. PLAYER CAPABILITIES
    // ==========================================
    {
      id: 'player-1',
      category: 'player',
      categoryLabel: 'Player',
      badgeTone: 'accent',
      question:
        'What can players do inside the Character Sheet (Player Dashboard)?',
      answerHtml: `
        <p>The <strong>Player Dashboard (<code>/player</code>)</strong> provides a complete interactive character sheet with 4 focused tabs:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>📜 Skills &amp; Checks:</strong> Roll Ability Checks, Saving Throws, and all 18 Skills in one click, with <em>Proficient Only</em> filter, proficiency/expertise toggles, and <strong>Advantage / Normal / Disadvantage</strong> selector.</li>
          <li><strong>⚔️ Combat &amp; Inventory:</strong> Full weapon management (Attack + Damage rolls, 2024 Weapon Masteries, Class Combat riders like <em>Sneak Attack</em>, <em>Divine Smite</em>, <em>Rage</em>), Class Resources (Ki/Focus Points, Second Wind, Channel Divinity), 1-tap <strong>Potions of Healing</strong> with auto-roll &amp; inventory decrement, Equipped/Attuned item slots (up to 3 attunements), and coin tracker (CP, SP, EP, GP, PP).</li>
          <li><strong>✨ Spells &amp; Features:</strong> Full Grimoire with level filters (Cantrips–9th Level), <em>Prepared / Concentration / Ritual</em> filters, 1-tap <strong>Cast Spell</strong> (consuming spell slots or casting Rituals slot-free), Warlock Pact Magic slots, and collapsible Features &amp; Traits.</li>
          <li><strong>📖 Lore &amp; Roleplay:</strong> View and edit Backstory, Personality Traits, Ideals, Bonds, Flaws, Languages, and Tool Proficiencies.</li>
        </ul>
      `,
      tags: ['player', 'sheet', 'skills', 'combat', 'spells', 'inventory', 'currency', 'attunement'],
    },
    {
      id: 'player-2',
      category: 'player',
      categoryLabel: 'Player',
      badgeTone: 'accent',
      question:
        'How do Short Rest, Long Rest, Hit Dice, Conditions, and Sheet Editing work?',
      answerHtml: `
        <p>Players have full control over recovery and sheet edits:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>⛺ Short Rest Modal:</strong> Choose how many Hit Dice to spend (including multiclass die sizes d6/d8/d10/d12), automatically roll healing + CON modifier, and recharge Warlock Pact Magic slots plus short-rest resources.</li>
          <li><strong>🌙 Long Rest:</strong> Restores full HP, recharges all Spell Slots and long-rest resources, and recovers spent Hit Dice (up to half in 2014 Edition, all Hit Dice in 2024 Revision).</li>
          <li><strong>🔥 Conditions &amp; Concentration Modal:</strong> Toggle conditions (Poisoned, Blinded, Prone, Charmed, etc.) and track your active Concentration spell.</li>
          <li><strong>✎ Edit Sheet &amp; ⚡ Quick Edit:</strong> Edit all hero fields via the full modal or inline on the sheet, backed by optimistic locking (version checks) to prevent overwrite conflicts.</li>
        </ul>
      `,
      tags: ['player', 'short rest', 'long rest', 'hit dice', 'conditions', 'edit sheet'],
    },
    {
      id: 'player-3',
      category: 'player',
      categoryLabel: 'Player',
      badgeTone: 'accent',
      question:
        'How does a Player interact with the Campaign and DM in real time?',
      answerHtml: `
        <p>Once a character joins a Campaign via <strong>🔑 Join Campaign (Invite Code)</strong>:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>Real-Time WebSocket Sync:</strong> Any HP or Condition change made by the DM updates the player's sheet instantaneously with a live toast notification.</li>
          <li><strong>🎲 DM Roll Requests:</strong> When the DM requests a roll (e.g., <em>Stealth Check</em> or <em>Wisdom Save</em>), an interactive 60-second modal pops up with Advantage/Disadvantage and Situational Bonus controls, sending your result back to the DM. Missed requests can still be rolled afterward from the Inbox.</li>
          <li><strong>💬 Whisper Inbox &amp; Quick Replies:</strong> Private messaging with the DM, table-wide broadcasts (<em>All</em>), quick-reply chips, and message reporting.</li>
          <li><strong>🧪 Campaign Homebrew:</strong> Instant access to add DM-created campaign spells and custom items directly into your sheet.</li>
        </ul>
      `,
      tags: ['player', 'campaign', 'invite code', 'websocket', 'roll request', 'whisper'],
    },

    // ==========================================
    // 3. MOBILE COMPANION (#170-#175)
    // ==========================================
    {
      id: 'companion-1',
      category: 'companion',
      categoryLabel: 'Mobile Companion',
      badgeTone: 'success',
      question:
        'What is the In-Person Mobile Companion and how does it adapt to phones & tablets?',
      answerHtml: `
        <p>On phone and tablet screens (<code>&lt; 1024px</code>), the app automatically switches into a streamlined <strong>In-Person Player Companion</strong>:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>Bottom Action Dock (5 Tabs):</strong> Thumb-friendly switching between <em>Hero</em>, <em>Combat</em>, <em>Skills</em>, <em>Spells</em>, and <em>Table</em> (with unread message badges), plus the quick <strong>🎲 Quick Dice</strong> trigger.</li>
          <li><strong>Haptic Feedback &amp; Wake Lock:</strong> Physical vibration feedback on rolls/damage and optional Screen Wake Lock so your sheet stays visible at the tabletop.</li>
          <li><strong>Automatic Reconnect Sync:</strong> When waking your phone from lock screen, the WebSocket reconnects automatically and pulls missed whispers or pending roll requests.</li>
        </ul>
      `,
      tags: ['mobile', 'companion', 'action dock', 'haptics', 'wake lock'],
    },
    {
      id: 'companion-2',
      category: 'companion',
      categoryLabel: 'Mobile Companion',
      badgeTone: 'success',
      question:
        'How do Turn Alerts, Concentration Checks, and the Quick-Dice Drawer work on mobile?',
      answerHtml: `
        <ul class="list-disc list-inside space-y-1">
          <li><strong>⚔️ Turn Alerts:</strong> Pulsing green banner + vibration alert when it is your turn (<em>It's Your Turn!</em>) and a gold prep banner when you are next (<em>On Deck</em>).</li>
          <li><strong>🧠 Concentration Check Prompt:</strong> Whenever you take damage while concentrating on a spell (even if absorbed by Temp HP), a prompt appears with the exact DC (<code>max(10, damage/2)</code>) and lets you roll your CON Saving Throw (including Proficiency &amp; active roll mode) or confirm a physical die check.</li>
          <li><strong>🎲 Quick-Dice Drawer:</strong> Fast d4–d100 dice tray supporting Advantage/Disadvantage even on mixed pools (e.g., <code>1d20 + 1d4</code> for <em>Guidance/Bless</em>), auto-resetting roll mode, and DM/party visibility controls.</li>
        </ul>
      `,
      tags: ['turn alert', 'concentration', 'quick dice', 'guidance', 'advantage'],
    },

    // ==========================================
    // 4. CHARACTER FORGE & IMPORTS
    // ==========================================
    {
      id: 'forge-1',
      category: 'forge',
      categoryLabel: 'Character Forge',
      badgeTone: 'accent',
      question:
        'How do Character Creation (AI & Manual) and Import/Export work?',
      answerHtml: `
        <ul class="list-disc list-inside space-y-1">
          <li><strong>🤖 AI Character Forge:</strong> Create a complete character from a natural-language prompt with automatic stats, spells, equipment, and backstory.</li>
          <li><strong>🛠️ Manual Character Forge + AI Enrich:</strong> Step-by-step builder for Race/Species, Class, Subclass, Background, Ability Scores, Skills, Feats, and Spells, with optional AI narrative enrichment.</li>
          <li><strong>📥 Multi-Platform Import:</strong> Import characters from <strong>D&amp;D Beyond</strong> (URL/ID), <strong>Foundry VTT</strong> (JSON), and official <strong>PDF Character Sheets</strong>.</li>
          <li><strong>📄 PDF Export:</strong> Export any hero into a pre-filled official PDF character sheet with live preview.</li>
        </ul>
      `,
      tags: ['forge', 'ai', 'manual', 'import', 'dndbeyond', 'foundry', 'pdf'],
    },
    {
      id: 'forge-2',
      category: 'forge',
      categoryLabel: 'Character Forge',
      badgeTone: 'accent',
      question:
        'How do Level-Up, Multiclassing, Rules Validation, and the AI Strategy Guide work?',
      answerHtml: `
        <ul class="list-disc list-inside space-y-1">
          <li><strong>⚡ Level-Up &amp; Multiclassing Engine:</strong> Level progression up to Level 20, multiclass prerequisite checks, HP choice (Roll or Fixed Average), subclass unlocks, ASI (+2 or +1/+1) or Feats, and automatic Multiclass Spellcaster Slot computation.</li>
          <li><strong>✅ Rules Validation &amp; Auto-Fix:</strong> Validates builds deterministically against 2014/2024 rules and offers 1-click Auto-Fix remediation.</li>
          <li><strong>🎨 AI Portrait &amp; 🧠 Playstyle Guide:</strong> Generates custom character portraits and tailored tactical combat guides for your hero.</li>
        </ul>
      `,
      tags: ['level up', 'multiclass', 'validation', 'autofix', 'portrait', 'strategy'],
    },

    // ==========================================
    // 5. VTT & HOMEBREW
    // ==========================================
    {
      id: 'vtt-1',
      category: 'vtt',
      categoryLabel: 'VTT & Homebrew',
      badgeTone: 'gold',
      question:
        'How does the 2D Virtual Tabletop (VTT Grid, Scenes, Fog of War & Assets) work?',
      answerHtml: `
        <ul class="list-disc list-inside space-y-1">
          <li><strong>🗺️ Multi-Scene Management:</strong> Create multiple scenes per campaign, upload custom battlemap images (Assets), switch the live active scene for all players, and track Scene History.</li>
          <li><strong>🌫️ Fog of War:</strong> Dynamic grid/polygon Fog of War (Reveal / Hide cells or Reveal All / Hide All) so players only see explored rooms.</li>
          <li><strong>♟️ Live Tokens:</strong> Place player and monster tokens (1x1, 2x2, etc.), toggle hidden tokens for invisible/ambush enemies, and drag-and-drop move live over WebSockets.</li>
        </ul>
      `,
      tags: ['vtt', 'scenes', 'fog of war', 'tokens', 'maps', 'grid'],
    },
    {
      id: 'vtt-2',
      category: 'vtt',
      categoryLabel: 'VTT & Homebrew',
      badgeTone: 'gold',
      question: 'How does the Homebrew Forge work for DMs and Players?',
      answerHtml: `
        <ul class="list-disc list-inside space-y-1">
          <li><strong>🧪 AI Homebrew Creation:</strong> DMs can generate custom Spells, Weapons, Magic Items, Monsters, and Feats from an idea prompt.</li>
          <li><strong>📡 Campaign Sharing:</strong> Any Homebrew item saved to a campaign becomes available to campaign players via WebSockets so they can equip or prepare it directly.</li>
          <li><strong>📦 Import / Export (JSON &amp; PDF):</strong> Export an entire Homebrew collection as printable PDF or shareable JSON.</li>
        </ul>
      `,
      tags: ['homebrew', 'custom spells', 'custom items', 'monsters', 'pdf export'],
    },

    // ==========================================
    // 6. RULES & AI ARBITER
    // ==========================================
    {
      id: 'rules-1',
      category: 'rules',
      categoryLabel: 'Rules & AI Arbiter',
      badgeTone: 'accent',
      question:
        'What features do the Rules Library and AI Arbiter provide?',
      answerHtml: `
        <ul class="list-disc list-inside space-y-1">
          <li><strong>📚 SRD Compendium:</strong> Instant search across Classes, Subclasses, Spells, Feats, Races/Species, Backgrounds, and Equipment.</li>
          <li><strong>⚖️ 2014 Legacy vs 2024 Revision (5.5e) Comparison:</strong> Side-by-side AI rules comparator breaking down exact mechanical differences between 2014 and 2024 for any spell, feature, or rule.</li>
          <li><strong>🤖 AI Rules Arbiter:</strong> Answers complex rules questions, interactions, and edge cases scoped to your active edition.</li>
        </ul>
      `,
      tags: ['rules', 'srd', '2014', '2024', 'compare', 'ai arbiter'],
    },

    // ==========================================
    // 7. ADMIN & SECURITY
    // ==========================================
    {
      id: 'admin-1',
      category: 'admin',
      categoryLabel: 'Admin & Security',
      badgeTone: 'danger',
      question:
        'What moderation, security, and management controls does the Admin Workspace provide?',
      answerHtml: `
        <ul class="list-disc list-inside space-y-1">
          <li><strong>👤 User Management &amp; Pagination:</strong> Search registered users, paginate (10/25/50 per page), and view hero/campaign counts.</li>
          <li><strong>🟢 Live Online Presence:</strong> Real-time <code>● Online / ○ Offline</code> indicator combining active WebSocket connections and recent API activity.</li>
          <li><strong>🗑️ Cascading User Deletion with Preview:</strong> Preview every impacted record before deleting a user (characters, portraits, memberships, archived whispers) while protecting active campaigns.</li>
          <li><strong>🚩 Whisper Reports Moderation:</strong> Review user reports with full message context and resolve/dismiss with audit notes.</li>
          <li><strong>🔒 Security &amp; Rate Limiting:</strong> JWT protection with <code>iat</code> token revocation checks, SlowAPI rate limiting on Auth/AI endpoints, magic-byte validation on file uploads (PDF/Audio/Images), and strict DM/Player RBAC guards.</li>
        </ul>
      `,
      tags: ['admin', 'pagination', 'online', 'delete cascade', 'moderation', 'security'],
    },
  ];

  filteredFaqItems = computed(() => {
    const q = this.searchQuery().trim().toLowerCase();
    const cat = this.selectedCategory();

    return this.faqItems.filter((item) => {
      if (!q) {
        return item.category === cat;
      }
      return (
        item.question.toLowerCase().includes(q) ||
        item.answerHtml.toLowerCase().includes(q) ||
        item.categoryLabel.toLowerCase().includes(q) ||
        item.tags.some((t) => t.toLowerCase().includes(q))
      );
    });
  });

  /** Questions per axis, for the counts in the category nav. */
  categoryCount(categoryId: string): number {
    return this.faqItems.filter((item) => item.category === categoryId).length;
  }

  readonly activeCategory = computed(
    () => this.categories.find((cat) => cat.id === this.selectedCategory()) ?? this.categories[0]
  );

  /** Every question in the current view is open: the toggle offers "collapse". */
  readonly allExpanded = computed(() => {
    const items = this.filteredFaqItems();
    const open = this.openQuestions();
    return items.length > 0 && items.every((item) => open.has(item.id));
  });

  toggleAll(): void {
    if (this.allExpanded()) this.collapseAll();
    else this.expandAll();
  }

  /** Category label without its leading emoji, for headings that show the icon separately. */
  categoryName(label: string): string {
    return label.replace(/^\S+\s+/, '');
  }

  isQuestionOpen(id: string): boolean {
    return this.openQuestions().has(id);
  }

  toggleQuestion(id: string): void {
    const next = new Set(this.openQuestions());
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    this.openQuestions.set(next);
  }

  expandAll(): void {
    const allIds = new Set(this.filteredFaqItems().map((i) => i.id));
    this.openQuestions.set(allIds);
  }

  collapseAll(): void {
    this.openQuestions.set(new Set());
  }

  selectCategory(catId: string): void {
    this.selectedCategory.set(catId);
    if (this.searchQuery()) {
      this.searchQuery.set('');
    }
  }
}
