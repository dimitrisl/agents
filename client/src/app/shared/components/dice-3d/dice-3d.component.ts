import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  EventEmitter,
  Input,
  NgZone,
  OnChanges,
  OnDestroy,
  Output,
  SimpleChanges,
  ViewChild,
} from '@angular/core';
import * as THREE from 'three';
import {
  Body,
  ContactMaterial,
  GSSolver,
  Material as PhysicsMaterial,
  NaiveBroadphase,
  Plane,
  Vec3,
  World,
} from 'cannon-es';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import {
  PreparedShape,
  buildShape,
  flattenRest,
  kindForSides,
  labelTexture,
  restingFace,
} from './dice-shapes';

/** Recorded transform per simulation step: position (3) + quaternion (4). */
const STRIDE = 7;
const STEP = 1 / 60;
const MAX_STEPS = 300;
const MAX_DICE = 8;
const PLAYBACK_RATE = 1.25;
/** Frames spent easing a cocked die onto its face. */
const SETTLE_FRAMES = 20;
/** Step at which leftover energy starts being damped away. */
const CALM_STEP = 130;

interface DiceThrow {
  frames: Float32Array;
  steps: number;
  finalQuaternion: THREE.Quaternion;
}

@Component({
  selector: 'app-dice-3d',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: '<canvas #canvas class="dice-canvas"></canvas>',
  styles: [`
    :host {
      display: block;
      height: 100%;
      overflow: hidden;
      position: relative;
      width: 100%;
    }

    /* Taken out of flow on purpose: setSize() writes the canvas width/height
       attributes, and if the canvas could size its own parent that would feed
       straight back into the ResizeObserver and grow without bound. */
    .dice-canvas {
      display: block;
      height: 100%;
      inset: 0;
      position: absolute;
      width: 100%;
    }
  `],
})
export class Dice3dComponent implements AfterViewInit, OnChanges, OnDestroy {
  /** Individual die results, in the order they should be shown. */
  @Input() values: number[] = [];
  @Input() sides = 20;
  /** Bumped by the caller to replay the same numbers as a fresh throw. */
  @Input() rollKey = 0;
  @Input() accent = '#d9b355';
  @Input() crit: 'success' | 'fail' | null = null;

  /** All dice have come to rest. */
  @Output() settled = new EventEmitter<void>();
  /** WebGL is unavailable — the caller should fall back to the flat die. */
  @Output() unsupported = new EventEmitter<void>();

  @ViewChild('canvas', { static: true }) canvasRef!: ElementRef<HTMLCanvasElement>;

  private renderer?: THREE.WebGLRenderer;
  private scene?: THREE.Scene;
  private camera?: THREE.PerspectiveCamera;
  private floor?: THREE.Mesh;
  private keyLight?: THREE.DirectionalLight;
  private rimLight?: THREE.DirectionalLight;
  private accentLight?: THREE.DirectionalLight;

  private dice: THREE.Group[] = [];
  private throws: DiceThrow[] = [];
  private disposables: (THREE.BufferGeometry | THREE.Material)[] = [];

  private arenaX = 3.2;
  private arenaZ = 3.2;
  private frameHandle = 0;
  private startTime = 0;
  private hasSettled = false;
  private critIntensity = 0;
  private resizeObserver?: ResizeObserver;
  private started = false;
  private viewWidth = 0;
  private viewHeight = 0;
  private environment?: THREE.Texture;
  private labelMaterials = new Map<string, THREE.MeshStandardMaterial>();
  private readonly poseA = new THREE.Quaternion();
  private readonly poseB = new THREE.Quaternion();

  constructor(private host: ElementRef<HTMLElement>, private zone: NgZone) {}

  ngAfterViewInit(): void {
    if (!this.initScene()) {
      this.unsupported.emit();
      return;
    }

    // The arena size decides where the walls go, so wait for a real layout
    // before throwing anything.
    this.resizeObserver = new ResizeObserver(() => {
      if (!this.layout()) return;
      if (!this.started) {
        this.started = true;
        this.throwDice();
      }
    });
    this.resizeObserver.observe(this.host.nativeElement);
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (!this.renderer || !this.started) return;
    if (changes['values'] || changes['rollKey'] || changes['sides'] || changes['crit']) {
      this.throwDice();
    }
  }

  ngOnDestroy(): void {
    cancelAnimationFrame(this.frameHandle);
    this.resizeObserver?.disconnect();
    this.clearDice();
    this.environment?.dispose();
    this.floor?.geometry.dispose();
    (this.floor?.material as THREE.Material | undefined)?.dispose();
    this.renderer?.dispose();
  }

  // ---------------------------------------------------------------- scene

  private initScene(): boolean {
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        canvas: this.canvasRef.nativeElement,
        alpha: true,
        antialias: true,
        powerPreference: 'high-performance',
      });
    } catch {
      return false;
    }

    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.3;
    this.renderer = renderer;

    const scene = new THREE.Scene();
    this.scene = scene;
    // Long lens, near top-down: keeps the dice from skewing towards the edges
    // and puts the read face square to the viewer.
    this.camera = new THREE.PerspectiveCamera(24, 1, 0.1, 200);

    // Metal needs something to reflect, otherwise the dice render almost black.
    const pmrem = new THREE.PMREMGenerator(renderer);
    this.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environment = this.environment;
    pmrem.dispose();

    scene.add(new THREE.AmbientLight(0xffffff, 0.45));

    const key = new THREE.DirectionalLight(0xfff4de, 3.4);
    key.castShadow = true;
    key.shadow.mapSize.set(1024, 1024);
    key.shadow.bias = -0.0009;
    scene.add(key);
    this.keyLight = key;

    // Cool rim from behind so the silhouette separates from the dark card.
    const rim = new THREE.DirectionalLight(0xbcd2ff, 2.2);
    scene.add(rim);
    this.rimLight = rim;

    const accentLight = new THREE.DirectionalLight(new THREE.Color(this.accent), 1.4);
    scene.add(accentLight);
    this.accentLight = accentLight;

    // Shadow-only floor so the toast background stays visible underneath.
    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(40, 40),
      new THREE.ShadowMaterial({ opacity: 0.55 }),
    );
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    scene.add(floor);
    this.floor = floor;

    return true;
  }

  /** Returns true once the host has a real size and the view is framed. */
  private layout(): boolean {
    const el = this.host.nativeElement;
    const width = el.clientWidth;
    const height = el.clientHeight;
    if (!width || !height || !this.renderer || !this.camera) return false;

    // Second guard against a resize loop: never touch the canvas unless the box
    // it lives in actually changed size.
    if (width === this.viewWidth && height === this.viewHeight) return true;
    this.viewWidth = width;
    this.viewHeight = height;

    this.renderer.setSize(width, height, false);

    const aspect = width / height;
    this.arenaZ = 2.8;
    this.arenaX = Math.max(2.8, this.arenaZ * aspect);

    const camera = this.camera;
    camera.aspect = aspect;
    const distance = (this.arenaZ * 1.22) / Math.tan((camera.fov * Math.PI) / 360);
    camera.position.set(0, distance * 0.975, distance * 0.22);
    camera.lookAt(0, 0, 0);
    camera.updateProjectionMatrix();

    if (this.keyLight) {
      this.keyLight.position.set(this.arenaX * 0.5, 9, this.arenaZ * 1.4);
      const shadow = this.keyLight.shadow.camera;
      shadow.left = -this.arenaX * 1.6;
      shadow.right = this.arenaX * 1.6;
      shadow.top = this.arenaZ * 2;
      shadow.bottom = -this.arenaZ * 2;
      shadow.near = 1;
      shadow.far = 30;
      shadow.updateProjectionMatrix();
    }

    this.rimLight?.position.set(-this.arenaX * 0.6, 3.2, -this.arenaZ * 1.8);
    this.accentLight?.position.set(-this.arenaX, 2.2, this.arenaZ * 1.2);
    this.renderer.render(this.scene!, camera);
    return true;
  }

  // ---------------------------------------------------------------- rolling

  private throwDice(): void {
    if (!this.scene || !this.renderer) return;

    cancelAnimationFrame(this.frameHandle);
    this.clearDice();
    this.hasSettled = false;
    this.critIntensity = 0;

    this.rimLight?.color.set(this.accent);

    const values = (this.values?.length ? this.values : [1]).slice(0, MAX_DICE);
    const kind = kindForSides(this.sides);
    const radius = this.diceRadius(values.length);
    const shape = buildShape(kind, radius);
    this.disposables.push(shape.geometry);

    this.throws = this.simulate(values.length, shape, radius);
    this.dice = values.map((value, index) =>
      this.buildDie(shape, value, this.throws[index].finalQuaternion),
    );
    this.dice.forEach((die) => this.scene!.add(die));

    this.applyFrame(0);

    if (this.prefersReducedMotion()) {
      this.applyFrame(Math.max(...this.throws.map((t) => t.steps)) - 1);
      this.renderer.render(this.scene, this.camera!);
      this.hasSettled = true;
      this.critIntensity = 1;
      setTimeout(() => this.zone.run(() => this.settled.emit()));
      return;
    }

    this.startTime = performance.now();
    this.zone.runOutsideAngular(() => this.animate());
  }

  private diceRadius(count: number): number {
    if (count <= 1) return 1.45;
    if (count <= 2) return 1.25;
    if (count <= 4) return 1.0;
    return 0.82;
  }

  private prefersReducedMotion(): boolean {
    return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true;
  }

  // ---------------------------------------------------------------- physics

  private simulate(count: number, shape: PreparedShape, radius: number): DiceThrow[] {
    const world = new World({ gravity: new Vec3(0, -40, 0), allowSleep: true });
    world.broadphase = new NaiveBroadphase();
    (world.solver as GSSolver).iterations = 16;

    // Felt-like floor, but springy barriers: dice are meant to carom off the
    // rails and keep travelling rather than dying where they hit.
    const floorMaterial = new PhysicsMaterial('floor');
    const barrierMaterial = new PhysicsMaterial('barrier');
    const diceMaterial = new PhysicsMaterial('dice');
    world.addContactMaterial(
      new ContactMaterial(floorMaterial, diceMaterial, { friction: 0.5, restitution: 0.4 }),
    );
    world.addContactMaterial(
      new ContactMaterial(barrierMaterial, diceMaterial, { friction: 0.4, restitution: 0.92 }),
    );
    world.addContactMaterial(
      new ContactMaterial(diceMaterial, diceMaterial, { friction: 0.35, restitution: 0.45 }),
    );

    const floor = new Body({ mass: 0, shape: new Plane(), material: floorMaterial });
    floor.quaternion.setFromEuler(-Math.PI / 2, 0, 0);
    world.addBody(floor);

    // Keep the walls inside the framed area so a die resting against one is still
    // fully on screen, without squeezing the box tighter than the die itself.
    const wallX = Math.max(this.arenaX - radius * 0.6, radius * 1.3);
    const wallZ = Math.max(this.arenaZ - radius * 0.6, radius * 1.3);

    const walls: [number, number, number, Vec3, number][] = [
      [wallX, 0, 0, new Vec3(0, 1, 0), -Math.PI / 2],
      [-wallX, 0, 0, new Vec3(0, 1, 0), Math.PI / 2],
      [0, 0, wallZ, new Vec3(0, 1, 0), Math.PI],
      [0, 0, -wallZ, new Vec3(0, 1, 0), 0],
    ];
    walls.forEach(([x, y, z, axis, angle]) => {
      const wall = new Body({ mass: 0, shape: new Plane(), material: barrierMaterial });
      wall.position.set(x, y, z);
      wall.quaternion.setFromAxisAngle(axis, angle);
      world.addBody(wall);
    });

    // Dice are hurled in from one corner and travel diagonally across the tray
    // rather than being dropped straight down — that lateral tumble is the feel.
    const side = Math.random() < 0.5 ? -1 : 1;
    const bodies: Body[] = [];

    const skew = this.rand(-0.45, 0.45);
    const dirX = -side * Math.cos(skew);
    const dirZ = Math.sin(skew);

    // Lay the handful out as a grid sized to what the tray can actually hold —
    // a row longer than the tray would start dice behind the wall.
    const minGap = radius * 2.1;
    const spanX = Math.max(2 * (wallX - radius * 1.1), 0);
    const spanZ = Math.max(2 * (wallZ - radius * 1.1), 0);
    const maxColumns = Math.max(1, Math.floor(spanX / minGap) + 1);
    const maxLanes = Math.max(1, Math.floor(spanZ / minGap) + 1);
    const lanes = Math.min(maxLanes, Math.ceil(count / maxColumns));
    const columns = Math.ceil(count / lanes);
    const gapX = columns > 1 ? Math.min(radius * 2.4, spanX / (columns - 1)) : 0;
    const gapZ = lanes > 1 ? Math.min(radius * 2.4, spanZ / (lanes - 1)) : 0;

    const limitZ = Math.max(wallZ - radius * 1.1, 0);
    const halfSpread = ((lanes - 1) / 2) * gapZ;
    // Start on the upwind side of the diagonal so there is tray left to cross.
    const centerZ = THREE.MathUtils.clamp(
      -dirZ * wallZ * 0.55,
      -(limitZ - halfSpread),
      limitZ - halfSpread,
    );

    for (let i = 0; i < count; i++) {
      const body = new Body({
        mass: 320,
        shape: shape.physics,
        material: diceMaterial,
        allowSleep: true,
      });
      body.sleepSpeedLimit = 0.22;
      body.sleepTimeLimit = 0.3;
      body.linearDamping = 0.04;
      body.angularDamping = 0.09;

      // Start clear of the wall and of each other: any overlap at rest makes the
      // solver fling dice apart and the throw never travels.
      const lane = (i % lanes) - (lanes - 1) / 2;
      const column = Math.floor(i / lanes);

      body.position.set(
        side * (wallX - radius * 1.1 - column * gapX),
        radius * 2.3 + this.rand(0, 0.5),
        centerZ + lane * gapZ,
      );
      body.quaternion.setFromEuler(
        this.rand(0, Math.PI * 2),
        this.rand(0, Math.PI * 2),
        this.rand(0, Math.PI * 2),
      );

      const speed = this.rand(15, 20);
      body.velocity.set(dirX * speed, this.rand(-2, 0.5), dirZ * speed);

      // Spin about the horizontal axis square to the direction of travel, so the
      // die tumbles end over end along its path instead of spinning on the spot.
      const tumble = this.rand(11, 17);
      body.angularVelocity.set(
        -dirZ * tumble + this.rand(-3, 3),
        this.rand(-2.5, 2.5),
        dirX * tumble + this.rand(-3, 3),
      );

      world.addBody(body);
      bodies.push(body);
    }

    const tracks = bodies.map(() => new Float32Array(MAX_STEPS * STRIDE));
    let steps = 0;
    let quiet = 0;

    for (let step = 0; step < MAX_STEPS; step++) {
      // Dice leaning on each other can jitter forever. Past this point the throw
      // has been read anyway, so bleed off the leftover energy.
      if (step === CALM_STEP) {
        bodies.forEach((body) => {
          body.linearDamping = 0.4;
          body.angularDamping = 0.5;
        });
      }

      world.step(STEP);
      bodies.forEach((body, i) => {
        const offset = step * STRIDE;
        const track = tracks[i];
        track[offset] = body.position.x;
        track[offset + 1] = body.position.y;
        track[offset + 2] = body.position.z;
        track[offset + 3] = body.quaternion.x;
        track[offset + 4] = body.quaternion.y;
        track[offset + 5] = body.quaternion.z;
        track[offset + 6] = body.quaternion.w;
      });
      steps = step + 1;
      const atRest = bodies.every(
        (body) =>
          body.sleepState === Body.SLEEPING ||
          (body.velocity.lengthSquared() < 0.05 && body.angularVelocity.lengthSquared() < 0.1),
      );
      quiet = atRest ? quiet + 1 : 0;
      if (quiet > 6) break;
    }

    return bodies.map((body, i) => {
      const resting = new THREE.Quaternion(
        body.quaternion.x,
        body.quaternion.y,
        body.quaternion.z,
        body.quaternion.w,
      );
      const flat = flattenRest(shape, resting);
      this.blendToRest(tracks[i], steps, flat.quaternion, flat.supportHeight);
      return { frames: tracks[i], steps, finalQuaternion: flat.quaternion };
    });
  }

  /** Eases the tail of a recorded throw into a perfectly level resting pose. */
  private blendToRest(
    track: Float32Array,
    steps: number,
    target: THREE.Quaternion,
    supportHeight: number,
  ): void {
    const blend = Math.min(SETTLE_FRAMES, steps);
    const last = (steps - 1) * STRIDE;
    // Only drop the die onto its face if it actually came to rest on the floor —
    // a die perched on another one keeps its height.
    const onFloor = track[last + 1] < supportHeight * 1.6;
    const quaternion = new THREE.Quaternion();

    for (let k = 0; k < blend; k++) {
      const offset = (steps - blend + k) * STRIDE;
      const t = (k + 1) / blend;
      const eased = t * t * (3 - 2 * t);

      quaternion.set(track[offset + 3], track[offset + 4], track[offset + 5], track[offset + 6]);
      quaternion.slerp(target, eased);
      track[offset + 3] = quaternion.x;
      track[offset + 4] = quaternion.y;
      track[offset + 5] = quaternion.z;
      track[offset + 6] = quaternion.w;

      if (onFloor) {
        track[offset + 1] += (supportHeight - track[offset + 1]) * eased;
      }
    }
  }

  private rand(min: number, max: number): number {
    return min + Math.random() * (max - min);
  }

  // ---------------------------------------------------------------- meshes

  private buildDie(
    shape: PreparedShape,
    value: number,
    finalQuaternion: THREE.Quaternion,
  ): THREE.Group {
    const group = new THREE.Group();
    const critColor = this.crit === 'success' ? 0xffd77a : this.crit === 'fail' ? 0xff4b4b : 0x000000;

    // On a metal the base colour tints the reflection, so a dark colour reads as
    // black no matter how much light is in the scene. This is deliberately mid-tone.
    const bodyMaterial = new THREE.MeshStandardMaterial({
      color: this.crit === 'success' ? 0x7a6a4a : this.crit === 'fail' ? 0x6d4450 : 0x5f5a78,
      metalness: 0.62,
      roughness: 0.26,
      envMapIntensity: 1.5,
      flatShading: true,
      emissive: new THREE.Color(critColor),
      emissiveIntensity: 0,
    });
    this.disposables.push(bodyMaterial);

    const mesh = new THREE.Mesh(shape.geometry, bodyMaterial);
    mesh.castShadow = true;
    group.add(mesh);

    // A thin bright line along the real edges reads as a bevel and keeps the
    // silhouette crisp against the dark card.
    const edgeGeometry = new THREE.EdgesGeometry(shape.geometry, 4);
    const edgeMaterial = new THREE.LineBasicMaterial({
      color: 0xcfc6ee,
      transparent: true,
      opacity: 0.34,
    });
    this.disposables.push(edgeGeometry, edgeMaterial);
    group.add(new THREE.LineSegments(edgeGeometry, edgeMaterial));

    // The label layout is decided after the simulation, so the face that landed
    // face-up is the one carrying the value the game already rolled.
    const upFace = restingFace(shape, finalQuaternion);
    const labels = this.faceLabels(shape.faces.length, value, upFace);

    // Every face of these solids is congruent, so one plate geometry serves all.
    const size = Math.min(...shape.faceInradius) * 2 * shape.labelScale;
    const plateGeometry = new THREE.PlaneGeometry(size, size);
    this.disposables.push(plateGeometry);

    const basis = new THREE.Matrix4();
    const axisX = new THREE.Vector3();

    labels.forEach((label, faceIndex) => {
      const plate = new THREE.Mesh(plateGeometry, this.labelMaterial(label));
      const normal = shape.faceNormals[faceIndex];
      const up = shape.faceUp[faceIndex];
      axisX.crossVectors(up, normal);
      basis.makeBasis(axisX, up, normal);
      plate.quaternion.setFromRotationMatrix(basis);
      plate.position.copy(shape.faceCenters[faceIndex]).addScaledVector(normal, shape.radius * 0.01);
      group.add(plate);
    });

    return group;
  }

  /** Number materials are shared by every die in the same throw. */
  private labelMaterial(label: string): THREE.MeshStandardMaterial {
    const cached = this.labelMaterials.get(label);
    if (cached) return cached;

    const texture = labelTexture(label);
    const color = new THREE.Color(
      this.crit === 'success' ? 0xfff0c2 : this.crit === 'fail' ? 0xffb0b0 : 0xf3d78d,
    );
    const material = new THREE.MeshStandardMaterial({
      map: texture,
      transparent: true,
      color,
      emissive: color,
      emissiveMap: texture,
      emissiveIntensity: 0.42,
      metalness: 0.25,
      roughness: 0.3,
      depthWrite: false,
      polygonOffset: true,
      polygonOffsetFactor: -2,
      polygonOffsetUnits: -2,
    });

    this.labelMaterials.set(label, material);
    return material;
  }

  /** Distinct numbers for every face, with `value` on the face that lands up. */
  private faceLabels(faceCount: number, value: number, upFace: number): string[] {
    const pool: number[] = [];

    if (this.sides === faceCount) {
      for (let n = 1; n <= faceCount; n++) {
        if (n !== value) pool.push(n);
      }
    } else {
      // Odd die size (d100 and friends): fill the remaining faces with other
      // plausible results so only the landing face has to be exact.
      const used = new Set([value]);
      while (pool.length < faceCount - 1) {
        const candidate = 1 + Math.floor(Math.random() * this.sides);
        if (used.has(candidate)) continue;
        used.add(candidate);
        pool.push(candidate);
      }
    }

    for (let i = pool.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [pool[i], pool[j]] = [pool[j], pool[i]];
    }

    const labels: string[] = [];
    let cursor = 0;
    for (let i = 0; i < faceCount; i++) {
      labels.push(String(i === upFace ? value : pool[cursor++]));
    }
    return labels;
  }

  private clearDice(): void {
    this.dice.forEach((die) => this.scene?.remove(die));
    this.dice = [];
    this.labelMaterials.forEach((material) => material.dispose());
    this.labelMaterials.clear();
    this.disposables.forEach((item) => item.dispose());
    this.disposables = [];
  }

  // ---------------------------------------------------------------- playback

  private animate = (): void => {
    if (!this.renderer || !this.scene || !this.camera) return;

    const elapsed = (performance.now() - this.startTime) / 1000;
    const maxSteps = Math.max(...this.throws.map((t) => t.steps));
    const frame = (elapsed * PLAYBACK_RATE) / STEP;

    this.applyFrame(frame);

    if (frame >= maxSteps - 1 && !this.hasSettled) {
      this.hasSettled = true;
      this.zone.run(() => this.settled.emit());
    }

    if (this.hasSettled && this.crit && this.critIntensity < 1) {
      this.critIntensity = Math.min(1, this.critIntensity + 0.04);
      this.dice.forEach((die) => {
        const material = (die.children[0] as THREE.Mesh).material as THREE.MeshStandardMaterial;
        material.emissiveIntensity = this.critIntensity * 0.55;
      });
    }

    this.renderer.render(this.scene, this.camera);

    const done = this.hasSettled && (!this.crit || this.critIntensity >= 1);
    if (!done) {
      this.frameHandle = requestAnimationFrame(this.animate);
    }
  };

  /**
   * `frame` is fractional: the recording is 60 steps per second but the display
   * is not, so poses are interpolated instead of snapped to the nearest step.
   * Snapping is what makes a perfectly fine throw look like it drops frames.
   */
  private applyFrame(frame: number): void {
    this.dice.forEach((die, i) => {
      const track = this.throws[i];
      if (!track) return;

      const last = track.steps - 1;
      const exact = Math.min(Math.max(frame, 0), last);
      const step = Math.floor(exact);
      const next = Math.min(step + 1, last);
      const t = exact - step;

      const frames = track.frames;
      const a = step * STRIDE;
      const b = next * STRIDE;

      die.position.set(
        frames[a] + (frames[b] - frames[a]) * t,
        frames[a + 1] + (frames[b + 1] - frames[a + 1]) * t,
        frames[a + 2] + (frames[b + 2] - frames[a + 2]) * t,
      );

      this.poseA.set(frames[a + 3], frames[a + 4], frames[a + 5], frames[a + 6]);
      this.poseB.set(frames[b + 3], frames[b + 4], frames[b + 5], frames[b + 6]);
      die.quaternion.copy(this.poseA).slerp(this.poseB, t);
    });
  }
}
