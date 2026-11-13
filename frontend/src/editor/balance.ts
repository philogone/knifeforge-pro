/**
 * Mass and balance point of a knife drawn in the editor.
 *
 * Every closed part on a cut layer is a flat plate: mass = area × thickness × density. Holes
 * (hole layer) inside a part remove their share of that part's material. The balance point is
 * the mass-weighted centroid of all parts, i.e. where the knife balances on a finger when it
 * lies flat. Real knives are not flat plates (grinds, tapers, rounded scales): the result is an
 * estimate, good for comparing two designs or placing the balance at the first pin.
 *
 * Areas use the shoelace formula on outlines flattened to 0.01 mm.
 */

export type Ring = [number, number][];

export interface PlatePart {
  id: string;
  /** outline rings, even-odd: a ring inside another is a cut-out */
  rings: Ring[];
  thicknessMm: number;
  /** g/cm³ */
  density: number;
}

export interface MassResult {
  massG: number;
  /** balance point, mm; null when there is no mass */
  centre: [number, number] | null;
  parts: { id: string; areaMm2: number; massG: number }[];
}

/** signed area and first moments of a ring (shoelace) */
function ringMoments(ring: Ring): { a: number; mx: number; my: number } {
  let a = 0;
  let mx = 0;
  let my = 0;
  for (let i = 0; i < ring.length; i++) {
    const [x0, y0] = ring[i];
    const [x1, y1] = ring[(i + 1) % ring.length];
    const cross = x0 * y1 - x1 * y0;
    a += cross;
    mx += (x0 + x1) * cross;
    my += (y0 + y1) * cross;
  }
  return { a: a / 2, mx: mx / 6, my: my / 6 };
}

export function pointInRing([px, py]: [number, number], ring: Ring): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if (yi > py !== yj > py && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

/** Area (mm²) and centroid of even-odd rings: a ring nested an odd number of times is a hole. */
export function areaAndCentroid(rings: Ring[]): { area: number; centre: [number, number] } {
  let area = 0;
  let mx = 0;
  let my = 0;
  rings.forEach((ring, i) => {
    if (ring.length < 3) return;
    const depth = rings.filter((other, j) => j !== i && other.length >= 3 && pointInRing(ring[0], other)).length;
    const sign = depth % 2 === 0 ? 1 : -1;
    const m = ringMoments(ring);
    const orient = Math.sign(m.a) || 1; // make every ring count positively, then apply the nesting sign
    area += sign * orient * m.a;
    mx += sign * orient * m.mx;
    my += sign * orient * m.my;
  });
  return { area, centre: area > 0 ? [mx / area, my / area] : [0, 0] };
}

/** Mass (g) and balance point of plate parts. */
export function massProperties(parts: PlatePart[]): MassResult {
  let mass = 0;
  let mx = 0;
  let my = 0;
  const out: MassResult["parts"] = [];
  for (const part of parts) {
    const { area, centre } = areaAndCentroid(part.rings);
    // mm² × mm = mm³; g/cm³ → g/mm³ is ÷ 1000
    const m = area > 0 ? (area * part.thicknessMm * part.density) / 1000 : 0;
    out.push({ id: part.id, areaMm2: area, massG: m });
    mass += m;
    mx += m * centre[0];
    my += m * centre[1];
  }
  return { massG: mass, centre: mass > 0 ? [mx / mass, my / mass] : null, parts: out };
}

/** Typical densities (g/cm³) by material, used as the default for a part. */
export const DENSITIES = {
  carbon_steel: 7.85,
  stainless_steel: 7.75,
  titanium: 4.51,
  brass: 8.5,
  copper: 8.96,
  nickel_silver: 8.7,
  mokume_gane: 8.7,
  g10: 1.85,
  micarta: 1.4,
  carbon_fiber: 1.6,
  wood: 0.75,
  stabilized_wood: 1.1,
  bone: 1.9,
} as const;

/** Best guess of a stock material's density from its type and name; the user can correct it. */
export function guessDensity(m: { category: string; metal_type: string | null; name: string; wood_species?: string | null }): number {
  if (m.metal_type && m.metal_type in DENSITIES) return DENSITIES[m.metal_type as keyof typeof DENSITIES];
  const name = m.name.toLowerCase();
  if (/g-?10|garolite/.test(name)) return DENSITIES.g10;
  if (/micarta/.test(name)) return DENSITIES.micarta;
  if (/carbon fib|fibre de carbone|fiber/.test(name)) return DENSITIES.carbon_fiber;
  if (/stabili/.test(name)) return DENSITIES.stabilized_wood;
  if (/os\b|bone|corne|horn|bois de cerf|antler/.test(name)) return DENSITIES.bone;
  if (/titan/.test(name)) return DENSITIES.titanium;
  if (/laiton|brass/.test(name)) return DENSITIES.brass;
  if (/maillechort|nickel/.test(name)) return DENSITIES.nickel_silver;
  if (m.category === "blade_steel" || m.category === "fitting") return DENSITIES.carbon_steel;
  if (m.category === "handle_material" || m.wood_species) return DENSITIES.wood;
  return DENSITIES.carbon_steel;
}
