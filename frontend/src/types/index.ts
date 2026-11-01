export type MaterialCategory = "blade_steel" | "handle_material" | "fitting" | "hardware" | "consumable";
export type DimensionType = "length" | "area" | "count";
export type MetalType = "stainless_steel" | "carbon_steel" | "titanium" | "mokume_gane" | "brass" | "copper" | "nickel_silver" | "other";
export type TreatmentType = "heat_treatment" | "damascus_etch" | "bluing" | "browning" | "acid_patina" | "other";
export type MaterialRole = "blade" | "handle" | "fitting" | "hardware" | "other";
export type KnifeType = "fixed" | "folder" | "kitchen" | "table" | "japanese" | "other";
export type OrderStatus = "draft" | "confirmed" | "completed" | "cancelled";
export type SawType = "band_saw" | "circular_saw" | "abrasive_cutoff" | "hacksaw" | "other";

export interface SawBlade {
  id: number;
  name: string;
  saw_type: SawType;
  diameter_mm: number | null;
  kerf_mm: number;
  notes: string | null;
  is_mock: boolean;
  created_at: string;
}

export interface Material {
  id: number;
  name: string;
  category: MaterialCategory;
  dimension_type: DimensionType;
  metal_type: MetalType | null;
  steel_grade: string | null;
  wood_species: string | null;
  wood_grade: string | null;
  piece_type: string | null;
  standard_length_mm: number | null;
  standard_width_mm: number | null;
  standard_thickness_mm: number | null;
  kerf_mm: number;
  saw_blade_id: number | null;
  saw_blade_name: string | null;
  quantity_in_stock: number;
  low_stock_threshold: number;
  unit_cost: number;
  is_mock: boolean;
  created_at: string;
}

export interface TreatmentStep {
  id?: number;
  step_order: number;
  description: string;
  temperature_c: number | null;
  duration_minutes: number | null;
  medium: string | null;
}

export interface TreatmentRecipe {
  id: number;
  name: string;
  treatment_type: TreatmentType;
  applies_to: string;
  notes: string | null;
  is_mock: boolean;
  created_at: string;
  steps: TreatmentStep[];
}

export interface KnifeModelMaterial {
  id?: number;
  material_id: number;
  material_name?: string;
  role: MaterialRole;
  blank_length_mm: number | null;
  blank_width_mm: number | null;
  blank_thickness_mm: number | null;
  quantity: number;
}

export interface KnifeModelTreatment {
  id?: number;
  treatment_recipe_id: number;
  treatment_recipe_name?: string;
  step_order: number;
}

export interface KnifeModel {
  id: number;
  name: string;
  knife_type: KnifeType;
  base_labor_hours: number;
  sale_price: number;
  margin_percent_override: number | null;
  is_mock: boolean;
  created_at: string;
  materials: KnifeModelMaterial[];
  treatments: KnifeModelTreatment[];
}

export interface OrderLine {
  id?: number;
  knife_model_id: number;
  knife_model_name?: string;
  quantity: number;
}

export interface Order {
  id: number;
  customer_name: string;
  customer_email: string | null;
  status: OrderStatus;
  notes: string | null;
  is_mock: boolean;
  created_at: string;
  lines: OrderLine[];
}

export interface MaterialFeasibility {
  material_id: number;
  material_name: string;
  unit: string;
  required: number;
  available: number;
  sufficient: boolean;
  shortfall: number;
}

export interface FeasibilityResult {
  feasible: boolean;
  materials: MaterialFeasibility[];
}

export interface YieldCalcResult {
  pieces_per_stock_unit: number;
  waste_per_stock_unit: number;
  waste_percentage: number;
  stock_units_needed: number;
  total_consumption: number;
  unit: string;
  grid_cols: number | null;
  grid_rows: number | null;
  rotated: boolean;
}

export interface CutPiece {
  length_mm: number;
  order_id: number;
  customer_name: string;
  knife_model_name: string;
}

export interface CutBar {
  pieces: CutPiece[];
  waste_mm: number;
}

export interface CostLine {
  material_id: number;
  material_name: string;
  role: MaterialRole;
  consumption: number;
  unit: string;
  unit_cost: number;
  line_cost: number;
}

export interface CostBreakdown {
  knife_model_id: number;
  knife_model_name: string;
  lines: CostLine[];
  total_material_cost: number;
  labor_hours: number;
  hourly_rate: number;
  labor_cost: number;
  cost_price: number;
  margin_percent: number;
  suggested_sale_price: number;
  current_sale_price: number;
}

export interface ShopSettings {
  hourly_rate: number;
  default_margin_percent: number;
}

export interface CandidateOrder {
  order_id: number;
  customer_name: string;
  status: OrderStatus;
  piece_count: number;
  total_length_mm: number;
}

export interface CuttingPlan {
  material_id: number;
  material_name: string;
  kerf_mm: number;
  stock_length_mm: number;
  total_pieces: number;
  bars_needed: number;
  total_waste_mm: number;
  waste_percentage: number;
  bars: CutBar[];
}

export interface MaterialDemand {
  material_id: number;
  material_name: string;
  unit: string;
  available: number;
  demand: number;
  shortfall: number;
}

export interface OrderSummary {
  order_id: number;
  customer_name: string;
  feasible: boolean;
  lines: string[];
}

export interface ProductionOverview {
  materials: MaterialDemand[];
  orders: OrderSummary[];
}
