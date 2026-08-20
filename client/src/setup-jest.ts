// The app runs with zone.js (not zoneless), so the specs get the zone-based
// TestBed environment. Swap this for `setupZonelessTestEnv` only if the app
// itself ever drops zone.js.
import { setupZoneTestEnv } from 'jest-preset-angular/setup-env/zone';

setupZoneTestEnv();
