import { defineStore } from "pinia";

import { apiFetch, apiFetchBlob, setToken } from "@/composables/useApi";
import type { DocNode } from "@/editor/types";
import type {
  CalibrationFeature,
  CalibrationResult,
  CandidateOrder,
  Customer,
  SalesDocument,
  StockMovement,
  CostBreakdown,
  CuttingPlan,
  Design,
  DesignSummary,
  DesignTemplate,
  FeasibilityResult,
  KnifeModel,
  Material,
  NestingCandidates,
  NestingRequest,
  NestingResult,
  Order,
  ProductionOverview,
  AutoBackup,
  Dashboard,
  SawBlade,
  ShopSettings,
  TreatmentRecipe,
  YieldCalcResult,
} from "@/types";

export const useAppStore = defineStore("app", {
  state: () => ({
    materials: [] as Material[],
    sawBlades: [] as SawBlade[],
    treatmentRecipes: [] as TreatmentRecipe[],
    knifeModels: [] as KnifeModel[],
    orders: [] as Order[],
    designs: [] as DesignSummary[],
    loading: false,
  }),
  actions: {
    async login(email: string, password: string) {
      const res = await apiFetch<{ access_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setToken(res.access_token);
    },

    /** desktop build only: the API answers 404 under Docker, where pg_dump does the job */
    async fetchAutoBackup() {
      return apiFetch<AutoBackup>("/admin/settings/auto-backup");
    },

    async saveAutoBackup(payload: Pick<AutoBackup, "enabled" | "directory" | "keep_days">) {
      return apiFetch<AutoBackup>("/admin/settings/auto-backup", { method: "PUT", body: JSON.stringify(payload) });
    },

    async runAutoBackup() {
      return apiFetch<AutoBackup>("/admin/settings/auto-backup/run", { method: "POST" });
    },

    /** desktop build: is the workshop's account still to be created? */
    async authStatus() {
      return apiFetch<{ needs_setup: boolean }>("/auth/status");
    },

    async setupAccount(email: string, password: string) {
      const res = await apiFetch<{ access_token: string }>("/auth/setup", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setToken(res.access_token);
    },

    async fetchMaterials() {
      this.materials = await apiFetch<Material[]>("/admin/materials");
    },
    async createMaterial(payload: Partial<Material>) {
      await apiFetch("/admin/materials", { method: "POST", body: JSON.stringify(payload) });
      await this.fetchMaterials();
    },
    async updateMaterial(id: number, payload: Partial<Material>) {
      await apiFetch(`/admin/materials/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
      await this.fetchMaterials();
    },
    async restockMaterial(id: number, quantity_delta: number, purchase_price: number | null = null, shipping_cost: number | null = null) {
      await apiFetch(`/admin/materials/${id}/restock`, {
        method: "POST",
        body: JSON.stringify({ quantity_delta, purchase_price, shipping_cost }),
      });
      await this.fetchMaterials();
    },
    async deleteMaterial(id: number) {
      await apiFetch(`/admin/materials/${id}`, { method: "DELETE" });
      await this.fetchMaterials();
    },
    async yieldCalc(id: number, blank_length_mm: number, blank_width_mm: number | null, quantity_needed: number) {
      return apiFetch<YieldCalcResult>(`/admin/materials/${id}/yield-calc`, {
        method: "POST",
        body: JSON.stringify({ blank_length_mm, blank_width_mm, quantity_needed }),
      });
    },
    async cuttingOptimizer(id: number, order_ids: number[] | null = null) {
      return apiFetch<CuttingPlan>(`/admin/materials/${id}/cutting-optimizer`, {
        method: "POST",
        body: JSON.stringify({ order_ids }),
      });
    },
    async cuttingCandidates(id: number) {
      return apiFetch<CandidateOrder[]>(`/admin/materials/${id}/cutting-candidates`);
    },

    async fetchSawBlades() {
      this.sawBlades = await apiFetch<SawBlade[]>("/admin/saw-blades");
    },
    async createSawBlade(payload: Partial<SawBlade>) {
      await apiFetch("/admin/saw-blades", { method: "POST", body: JSON.stringify(payload) });
      await this.fetchSawBlades();
    },
    async deleteSawBlade(id: number) {
      await apiFetch(`/admin/saw-blades/${id}`, { method: "DELETE" });
      await this.fetchSawBlades();
    },

    async fetchTreatmentRecipes() {
      this.treatmentRecipes = await apiFetch<TreatmentRecipe[]>("/admin/treatment-recipes");
    },
    async createTreatmentRecipe(payload: Partial<TreatmentRecipe>) {
      await apiFetch("/admin/treatment-recipes", { method: "POST", body: JSON.stringify(payload) });
      await this.fetchTreatmentRecipes();
    },
    async updateTreatmentRecipe(id: number, payload: Partial<TreatmentRecipe>) {
      await apiFetch(`/admin/treatment-recipes/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
      await this.fetchTreatmentRecipes();
    },
    async deleteTreatmentRecipe(id: number) {
      await apiFetch(`/admin/treatment-recipes/${id}`, { method: "DELETE" });
      await this.fetchTreatmentRecipes();
    },

    async fetchKnifeModels() {
      this.knifeModels = await apiFetch<KnifeModel[]>("/admin/knife-models");
    },
    async createKnifeModel(payload: Record<string, unknown>) {
      await apiFetch("/admin/knife-models", { method: "POST", body: JSON.stringify(payload) });
      await this.fetchKnifeModels();
    },
    async updateKnifeModel(id: number, payload: Record<string, unknown>) {
      await apiFetch(`/admin/knife-models/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
      await this.fetchKnifeModels();
    },
    async deleteKnifeModel(id: number) {
      await apiFetch(`/admin/knife-models/${id}`, { method: "DELETE" });
      await this.fetchKnifeModels();
    },
    async fetchCostBreakdown(id: number) {
      return apiFetch<CostBreakdown>(`/admin/knife-models/${id}/cost-breakdown`);
    },

    async fetchOrders() {
      this.orders = await apiFetch<Order[]>("/admin/orders");
    },
    async fetchOrder(id: number) {
      return apiFetch<Order>(`/admin/orders/${id}`);
    },
    async createOrder(payload: Record<string, unknown>) {
      await apiFetch("/admin/orders", { method: "POST", body: JSON.stringify(payload) });
      await this.fetchOrders();
    },
    async updateOrderLines(id: number, lines: { knife_model_id: number; quantity: number }[]) {
      await apiFetch(`/admin/orders/${id}`, { method: "PATCH", body: JSON.stringify({ lines }) });
    },
    async checkFeasibility(id: number) {
      return apiFetch<FeasibilityResult>(`/admin/orders/${id}/feasibility`);
    },
    async confirmOrder(id: number) {
      return apiFetch<Order>(`/admin/orders/${id}/confirm`, { method: "POST" });
    },
    async cancelOrder(id: number) {
      return apiFetch<Order>(`/admin/orders/${id}/cancel`, { method: "POST" });
    },
    async completeOrder(id: number) {
      return apiFetch<Order>(`/admin/orders/${id}/complete`, { method: "POST" });
    },
    async deleteOrder(id: number) {
      await apiFetch(`/admin/orders/${id}`, { method: "DELETE" });
      await this.fetchOrders();
    },

    async fetchDesigns(filter: { knife_model_id?: number; material_id?: number } = {}) {
      const params = new URLSearchParams();
      if (filter.knife_model_id) params.set("knife_model_id", String(filter.knife_model_id));
      if (filter.material_id) params.set("material_id", String(filter.material_id));
      const qs = params.toString();
      const list = await apiFetch<DesignSummary[]>(`/admin/designs${qs ? `?${qs}` : ""}`);
      if (!qs) this.designs = list;
      return list;
    },
    async fetchDesign(id: number) {
      return apiFetch<Design>(`/admin/designs/${id}`);
    },
    async fetchCalibrationFeatures() {
      return apiFetch<CalibrationFeature[]>("/admin/calibration/features");
    },
    async analyseCalibration(kerf_used_mm: number, measurements: Record<string, number>) {
      return apiFetch<CalibrationResult>("/admin/calibration/analyse", {
        method: "POST",
        body: JSON.stringify({ kerf_used_mm, measurements }),
      });
    },
    downloadCalibrationSheet(kerf: number, machine: string, material: string) {
      const params = new URLSearchParams({ kerf: String(kerf) });
      if (machine) params.set("machine", machine);
      if (material) params.set("material", material);
      return apiFetchBlob(`/admin/calibration/sheet.pdf?${params}`);
    },
    async fetchDesignTemplates() {
      return apiFetch<DesignTemplate[]>("/admin/designs/templates");
    },
    async createDesign(payload: Record<string, unknown>) {
      return apiFetch<Design>("/admin/designs", { method: "POST", body: JSON.stringify(payload) });
    },
    async updateDesign(id: number, payload: Record<string, unknown>) {
      return apiFetch<Design>(`/admin/designs/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
    },
    async duplicateDesign(id: number) {
      const copy = await apiFetch<Design>(`/admin/designs/${id}/duplicate`, { method: "POST" });
      await this.fetchDesigns();
      return copy;
    },
    async deleteDesign(id: number) {
      await apiFetch(`/admin/designs/${id}`, { method: "DELETE" });
      await this.fetchDesigns();
    },
    async offsetContours(contours: DocNode[][], distance_mm: number, join: "round" | "mitre" | "bevel") {
      const res = await apiFetch<{ contours: DocNode[][] }>("/admin/designs/geometry/offset", {
        method: "POST",
        body: JSON.stringify({ contours, distance_mm, join }),
      });
      return res.contours;
    },
    downloadDesignFile(id: number, kind: "export.svg" | "export.dxf", opts: { curves?: "polylines" | "arcs"; kerf?: number } = {}) {
      const qs = new URLSearchParams();
      if (opts.curves && kind === "export.dxf") qs.set("curves", opts.curves);
      if (opts.kerf) qs.set("kerf", String(opts.kerf));
      return apiFetchBlob(`/admin/designs/${id}/${kind}${qs.toString() ? `?${qs}` : ""}`);
    },
    /** the cut parts extruded to a thickness (mm), for 3D printing */
    downloadStl(id: number, thickness: number) {
      return apiFetchBlob(`/admin/designs/${id}/export.stl?thickness=${thickness}`);
    },
    /** the parts at true size on A4 / A3, tiled if needed, with punch marks */
    downloadPartsSheet(id: number, paper: "A4" | "A3") {
      return apiFetchBlob(`/admin/designs/${id}/parts.pdf?paper=${paper}`);
    },
    designPlan(id: number, params: Record<string, string | number | undefined>, download = false) {
      const qs = new URLSearchParams();
      for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") qs.set(k, String(v));
      if (download) qs.set("download", "true");
      return apiFetchBlob(`/admin/designs/${id}/plan.svg?${qs.toString()}`);
    },

    async nestingCandidates(materialId: number) {
      return apiFetch<NestingCandidates>(`/admin/nesting/candidates?material_id=${materialId}`);
    },
    async runNesting(request: NestingRequest) {
      return apiFetch<NestingResult>("/admin/nesting/run", { method: "POST", body: JSON.stringify(request) });
    },
    exportNesting(request: NestingRequest, format: "svg" | "dxf", sheet_index: number) {
      return apiFetchBlob("/admin/nesting/export", { method: "POST", body: JSON.stringify({ request, format, sheet_index }) });
    },

    async fetchProductionOverview() {
      return apiFetch<ProductionOverview>("/admin/production/overview");
    },

    async fetchDashboard() {
      return apiFetch<Dashboard>("/admin/dashboard");
    },

    async mockDataStatus() {
      return apiFetch<{ enabled: boolean }>("/admin/settings/mock-data");
    },
    async seedMockData() {
      return apiFetch<{ seeded: number }>("/admin/settings/mock-data/seed", { method: "POST" });
    },
    async clearMockData() {
      return apiFetch<{ removed: number }>("/admin/settings/mock-data/clear", { method: "POST" });
    },
    async downloadBackup() {
      return apiFetch<Record<string, unknown>>("/admin/settings/backup");
    },
    async restoreBackup(backup: unknown) {
      return apiFetch<{ restored: Record<string, number> }>("/admin/settings/restore", { method: "POST", body: JSON.stringify(backup) });
    },
    // ---- customers
    async fetchCustomers() {
      return apiFetch<Customer[]>("/admin/customers");
    },
    async fetchCustomer(id: number) {
      return apiFetch<Customer>(`/admin/customers/${id}`);
    },
    async saveCustomer(payload: Partial<Customer>, id?: number) {
      return id
        ? apiFetch<Customer>(`/admin/customers/${id}`, { method: "PUT", body: JSON.stringify(payload) })
        : apiFetch<Customer>("/admin/customers", { method: "POST", body: JSON.stringify(payload) });
    },
    async deleteCustomer(id: number) {
      return apiFetch(`/admin/customers/${id}`, { method: "DELETE" });
    },
    async exportCustomer(id: number) {
      return apiFetch<Record<string, unknown>>(`/admin/customers/${id}/export`);
    },
    async eraseCustomer(id: number) {
      return apiFetch<Customer>(`/admin/customers/${id}/erase`, { method: "POST" });
    },
    // ---- quotes, invoices, credit notes
    async fetchDocuments(filter: { kind?: string; customer_id?: number; order_id?: number } = {}) {
      const qs = new URLSearchParams();
      for (const [k, v] of Object.entries(filter)) if (v) qs.set(k, String(v));
      return apiFetch<SalesDocument[]>(`/admin/documents${qs.toString() ? `?${qs}` : ""}`);
    },
    async fetchDocument(id: number) {
      return apiFetch<SalesDocument>(`/admin/documents/${id}`);
    },
    async createDocument(payload: Record<string, unknown>) {
      return apiFetch<SalesDocument>("/admin/documents", { method: "POST", body: JSON.stringify(payload) });
    },
    async updateDocument(id: number, payload: Record<string, unknown>) {
      return apiFetch<SalesDocument>(`/admin/documents/${id}`, { method: "PUT", body: JSON.stringify(payload) });
    },
    async deleteDocument(id: number) {
      return apiFetch(`/admin/documents/${id}`, { method: "DELETE" });
    },
    async documentFromOrder(orderId: number, kind: "quote" | "invoice") {
      return apiFetch<SalesDocument>(`/admin/documents/from-order/${orderId}?kind=${kind}`, { method: "POST" });
    },
    async documentAction(id: number, action: "issue" | "credit-note" | "to-invoice") {
      return apiFetch<SalesDocument>(`/admin/documents/${id}/${action}`, { method: "POST" });
    },
    async documentStatus(id: number, status: string) {
      return apiFetch<SalesDocument>(`/admin/documents/${id}/status?status=${status}`, { method: "POST" });
    },
    documentPdf(id: number, download = false) {
      return apiFetchBlob(`/admin/documents/${id}/pdf${download ? "?download=true" : ""}`);
    },
    // ---- stock ledger
    async fetchMovements(materialId: number) {
      return apiFetch<StockMovement[]>(`/admin/materials/${materialId}/movements`);
    },
    async updateOrder(id: number, payload: Record<string, unknown>) {
      return apiFetch<Order>(`/admin/orders/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
    },
    async exportData() {
      return apiFetch<Record<string, unknown>>("/admin/settings/export");
    },
    async fetchShopSettings() {
      return apiFetch<ShopSettings>("/admin/settings/shop");
    },
    async updateShopSettings(payload: Partial<ShopSettings>) {
      return apiFetch<ShopSettings>("/admin/settings/shop", { method: "PATCH", body: JSON.stringify(payload) });
    },
  },
});
