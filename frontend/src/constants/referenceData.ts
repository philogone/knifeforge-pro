// Reference suggestions for free-text fields — starting points a maker can
// extend or ignore entirely, not a closed list (the software is free under the AGPL: users can
// freely modify this file for their own catalog).

export const STEEL_GRADE_SUGGESTIONS: string[] = [
  // Carbon steels
  "XC75", "XC100 (AISI 1095)", "80CrV2 (L2)", "90MnCrV8 (O2)", "15N20",
  "100Cr6 (AISI 52100)", "100MnCrW4 (O1)", "135Cr3 (W2)", "CPM 3V", "CPM Cru-Wear",
  // Stainless steels
  "Z40C13 (X46Cr13)", "14C28N", "VG10", "RWL34", "N690Co",
  // Damascus
  "Damas carbone", "Damas inoxydable", "Damas titane", "Mokume-gane",
];

export const WOOD_SPECIES_SUGGESTIONS: string[] = [
  "Noyer (Walnut)", "Frêne (Ash)", "Érable ronceux (Curly maple)", "Olivier (Olive)",
  "Buis (Boxwood)", "Ébène (Ebony)", "Palissandre (Rosewood)", "If (Yew)",
  "Chêne (Oak)", "Châtaignier (Chestnut)", "Bouleau (Birch)", "Amourette (Snakewood)",
];

export const WOOD_GRADE_SUGGESTIONS: string[] = [
  "AAA", "AA", "Ronce (Burl)", "Loupe", "Madré (Curly)", "Stabilisé (Stabilized)",
];

export const PIECE_TYPE_SUGGESTIONS: string[] = [
  "Jeu de plaquettes", "Quillon", "Mitre", "Rondelle de propreté", "Talon",
  "Rivet tubulaire", "Rivet plein", "Vis Corby", "Entretoise", "Clip de poche",
  "Axe de pliant", "Ressort (backspring)", "Écrou à sertir",
];

/** One colour per order state, shared by the list and the detail page. */
export const ORDER_STATUS_TAG: Record<"draft" | "confirmed" | "completed" | "cancelled", string> = {
  draft: "tag-neutral",
  confirmed: "tag-info",
  completed: "tag-success",
  cancelled: "tag-danger",
};

/** Quote / invoice / credit note states, one colour each (DESIGN.md tags). */
export const DOCUMENT_STATUS_TAG: Record<"draft" | "issued" | "accepted" | "refused" | "paid", string> = {
  draft: "tag-neutral",
  issued: "tag-info",
  accepted: "tag-success",
  refused: "tag-danger",
  paid: "tag-success",
};

