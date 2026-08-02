import * as THREE from 'three';
import { ConvexPolyhedron, Vec3 } from 'cannon-es';

export type DieKind = 'd4' | 'd6' | 'd8' | 'd10' | 'd12' | 'd20';

interface ShapeDef {
  /** Raw polyhedron vertices, any scale. Normalised to the requested radius on build. */
  vertices: number[][];
  /** Faces as cycles of vertex indices. Winding is corrected automatically. */
  faces: number[][];
  /** Number plate size as a fraction of the face inradius. */
  labelScale: number;
  /** Read the face pointing down instead of up (true d4 behaviour). */
  readDown?: boolean;
}

export interface PreparedShape {
  kind: DieKind;
  radius: number;
  faces: number[][];
  faceNormals: THREE.Vector3[];
  faceCenters: THREE.Vector3[];
  faceUp: THREE.Vector3[];
  faceInradius: number[];
  geometry: THREE.BufferGeometry;
  physics: ConvexPolyhedron;
  readDown: boolean;
  labelScale: number;
}

const PHI = (1 + Math.sqrt(5)) / 2;

function trapezohedron(): ShapeDef {
  // Pentagonal trapezohedron: 10 equatorial vertices in a zig-zag plus two apexes.
  // h is the zig-zag offset that keeps every kite face planar.
  const step = (Math.PI * 2) / 10;
  const k = Math.cos(step);
  const h = (1 - k) / (1 + k);

  const vertices: number[][] = [];
  for (let i = 0; i < 10; i++) {
    const b = i * step;
    vertices.push([Math.cos(b), Math.sin(b), h * (i % 2 ? 1 : -1)]);
  }
  vertices.push([0, 0, -1]); // 10: bottom apex
  vertices.push([0, 0, 1]); //  11: top apex

  const faces: number[][] = [];
  // Kites hanging off the top apex are centred on the low (even) equator vertices.
  for (let i = 0; i < 10; i += 2) {
    faces.push([11, (i + 9) % 10, i, (i + 1) % 10]);
  }
  for (let i = 1; i < 10; i += 2) {
    faces.push([10, (i + 9) % 10, i, (i + 1) % 10]);
  }

  return { vertices, faces, labelScale: 0.8 };
}

const SHAPE_DEFS: Record<DieKind, ShapeDef> = {
  d4: {
    vertices: [[1, 1, 1], [-1, -1, 1], [-1, 1, -1], [1, -1, -1]],
    faces: [[1, 2, 3], [0, 2, 1], [0, 1, 3], [0, 3, 2]],
    labelScale: 0.9,
    readDown: true,
  },
  d6: {
    vertices: [
      [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
      [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1],
    ],
    faces: [
      [0, 1, 2, 3], [4, 5, 6, 7], [1, 5, 6, 2],
      [0, 4, 7, 3], [3, 2, 6, 7], [0, 1, 5, 4],
    ],
    labelScale: 0.86,
  },
  d8: {
    vertices: [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]],
    faces: [
      [0, 2, 4], [2, 1, 4], [1, 3, 4], [3, 0, 4],
      [2, 0, 5], [1, 2, 5], [3, 1, 5], [0, 3, 5],
    ],
    labelScale: 0.86,
  },
  d10: trapezohedron(),
  d12: {
    vertices: [
      [0, 1 / PHI, PHI], [0, 1 / PHI, -PHI], [0, -1 / PHI, PHI], [0, -1 / PHI, -PHI],
      [PHI, 0, 1 / PHI], [PHI, 0, -1 / PHI], [-PHI, 0, 1 / PHI], [-PHI, 0, -1 / PHI],
      [1 / PHI, PHI, 0], [1 / PHI, -PHI, 0], [-1 / PHI, PHI, 0], [-1 / PHI, -PHI, 0],
      [1, 1, 1], [1, 1, -1], [1, -1, 1], [1, -1, -1],
      [-1, 1, 1], [-1, 1, -1], [-1, -1, 1], [-1, -1, -1],
    ],
    faces: [
      [2, 14, 4, 12, 0], [15, 9, 11, 19, 3], [16, 10, 17, 7, 6], [6, 7, 19, 11, 18],
      [6, 18, 2, 0, 16], [18, 11, 9, 14, 2], [1, 17, 10, 8, 13], [1, 13, 5, 15, 3],
      [13, 8, 12, 4, 5], [5, 4, 14, 9, 15], [0, 12, 8, 10, 16], [3, 19, 7, 17, 1],
    ],
    labelScale: 0.82,
  },
  d20: {
    vertices: [
      [-1, PHI, 0], [1, PHI, 0], [-1, -PHI, 0], [1, -PHI, 0],
      [0, -1, PHI], [0, 1, PHI], [0, -1, -PHI], [0, 1, -PHI],
      [PHI, 0, -1], [PHI, 0, 1], [-PHI, 0, -1], [-PHI, 0, 1],
    ],
    faces: [
      [0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11],
      [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8],
      [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9],
      [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1],
    ],
    labelScale: 0.85,
  },
};

/** Face count of every supported die, used to decide which shape a roll gets. */
export const KIND_FOR_SIDES: Record<number, DieKind> = {
  4: 'd4',
  6: 'd6',
  8: 'd8',
  10: 'd10',
  12: 'd12',
  20: 'd20',
};

export function kindForSides(sides: number): DieKind {
  return KIND_FOR_SIDES[sides] ?? (sides > 12 ? 'd20' : 'd10');
}

function newellNormal(face: number[], vertices: THREE.Vector3[]): THREE.Vector3 {
  const n = new THREE.Vector3();
  for (let i = 0; i < face.length; i++) {
    const a = vertices[face[i]];
    const b = vertices[face[(i + 1) % face.length]];
    n.x += (a.y - b.y) * (a.z + b.z);
    n.y += (a.z - b.z) * (a.x + b.x);
    n.z += (a.x - b.x) * (a.y + b.y);
  }
  return n.normalize();
}

function faceCentroid(face: number[], vertices: THREE.Vector3[]): THREE.Vector3 {
  const c = new THREE.Vector3();
  face.forEach((i) => c.add(vertices[i]));
  return c.divideScalar(face.length);
}

/** Smallest centroid-to-edge distance, i.e. how big a number plate can be. */
function faceInradius(face: number[], vertices: THREE.Vector3[], center: THREE.Vector3): number {
  let min = Infinity;
  const edge = new THREE.Vector3();
  const toCenter = new THREE.Vector3();
  for (let i = 0; i < face.length; i++) {
    const a = vertices[face[i]];
    const b = vertices[face[(i + 1) % face.length]];
    edge.subVectors(b, a);
    toCenter.subVectors(center, a);
    const t = THREE.MathUtils.clamp(toCenter.dot(edge) / edge.lengthSq(), 0, 1);
    const dist = toCenter.distanceTo(edge.clone().multiplyScalar(t));
    min = Math.min(min, dist);
  }
  return min;
}

export function buildShape(kind: DieKind, radius: number): PreparedShape {
  const def = SHAPE_DEFS[kind];

  const raw = def.vertices.map((v) => new THREE.Vector3(v[0], v[1], v[2]));
  const circumradius = raw.reduce((max, v) => Math.max(max, v.length()), 0);
  const vertices = raw.map((v) => v.multiplyScalar(radius / circumradius));

  // Force every face to wind counter-clockwise seen from outside (three.js and
  // cannon-es both need that), keeping vertex 0 in place so label orientation is stable.
  const faces = def.faces.map((face) => {
    const normal = newellNormal(face, vertices);
    const center = faceCentroid(face, vertices);
    return normal.dot(center) < 0 ? [face[0], ...face.slice(1).reverse()] : face.slice();
  });

  const faceNormals: THREE.Vector3[] = [];
  const faceCenters: THREE.Vector3[] = [];
  const faceUp: THREE.Vector3[] = [];
  const inradii: number[] = [];
  const positions: number[] = [];
  const normals: number[] = [];

  faces.forEach((face) => {
    const normal = newellNormal(face, vertices);
    const center = faceCentroid(face, vertices);
    faceNormals.push(normal);
    faceCenters.push(center);
    inradii.push(faceInradius(face, vertices, center));

    // "Up" for the printed number: towards the face's first vertex, projected onto the face.
    const up = new THREE.Vector3()
      .subVectors(vertices[face[0]], center)
      .projectOnPlane(normal)
      .normalize();
    faceUp.push(up);

    // Fan triangulation - every face here is convex.
    for (let i = 1; i < face.length - 1; i++) {
      const tri = [vertices[face[0]], vertices[face[i]], vertices[face[i + 1]]];
      tri.forEach((v) => {
        positions.push(v.x, v.y, v.z);
        normals.push(normal.x, normal.y, normal.z);
      });
    }
  });

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3));
  geometry.computeBoundingSphere();

  const physics = new ConvexPolyhedron({
    vertices: vertices.map((v) => new Vec3(v.x, v.y, v.z)),
    faces: faces.map((f) => f.slice()),
  });

  return {
    kind,
    radius,
    faces,
    faceNormals,
    faceCenters,
    faceUp,
    faceInradius: inradii,
    geometry,
    physics,
    readDown: def.readDown === true,
    labelScale: def.labelScale,
  };
}

const WORLD_UP = new THREE.Vector3(0, 1, 0);

/** Index of the face the die came to rest on for the given orientation. */
export function restingFace(shape: PreparedShape, quaternion: THREE.Quaternion): number {
  const dir = shape.readDown ? -1 : 1;
  let best = 0;
  let bestDot = -Infinity;
  const normal = new THREE.Vector3();

  shape.faceNormals.forEach((n, i) => {
    normal.copy(n).applyQuaternion(quaternion);
    const dot = normal.dot(WORLD_UP) * dir;
    if (dot > bestDot) {
      bestDot = dot;
      best = i;
    }
  });

  return best;
}

export interface FlatRest {
  /** Index of the face that is being read. */
  face: number;
  /** Orientation with that face perfectly level. */
  quaternion: THREE.Quaternion;
  /** Centre height of the die when it sits on that face. */
  supportHeight: number;
  /** 1 when the die already landed flat, lower the more it is cocked. */
  flatness: number;
}

/**
 * Physics happily leaves a die leaning on a wall or on another die. This nudges
 * the resting orientation so the read face is exactly level and the number is
 * unambiguous, which is what the eye expects once everything stops moving.
 */
export function flattenRest(shape: PreparedShape, quaternion: THREE.Quaternion): FlatRest {
  const face = restingFace(shape, quaternion);
  const target = new THREE.Vector3(0, shape.readDown ? -1 : 1, 0);
  const normal = shape.faceNormals[face].clone().applyQuaternion(quaternion);
  const correction = new THREE.Quaternion().setFromUnitVectors(normal, target);

  return {
    face,
    quaternion: correction.multiply(quaternion),
    supportHeight: Math.abs(shape.faceCenters[face].dot(shape.faceNormals[face])),
    flatness: normal.dot(target),
  };
}

const textureCache = new Map<string, THREE.CanvasTexture>();

/** White-on-transparent glyph, tinted by the material so one texture serves every die colour. */
export function labelTexture(label: string): THREE.CanvasTexture {
  const cached = textureCache.get(label);
  if (cached) return cached;

  const size = 256;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;

  const ctx = canvas.getContext('2d')!;
  ctx.clearRect(0, 0, size, size);
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';

  const fontSize = label.length > 2 ? size * 0.44 : label.length > 1 ? size * 0.56 : size * 0.72;
  ctx.font = `700 ${fontSize}px Georgia, "Times New Roman", serif`;

  // Dark halo first: the material tints the whole glyph, so a grey outline comes
  // out as a deeper shade of the number colour and lifts it off the metal.
  ctx.strokeStyle = '#2a2632';
  ctx.lineWidth = size * 0.05;
  ctx.lineJoin = 'round';
  ctx.strokeText(label, size / 2, size / 2);

  ctx.fillStyle = '#ffffff';
  ctx.fillText(label, size / 2, size / 2);

  // Underline the numbers you would otherwise misread upside down.
  if (label === '6' || label === '9') {
    const width = ctx.measureText(label).width * 0.72;
    const bar = Math.max(4, size * 0.032);
    ctx.fillRect((size - width) / 2, size / 2 + fontSize * 0.44, width, bar);
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  textureCache.set(label, texture);
  return texture;
}
