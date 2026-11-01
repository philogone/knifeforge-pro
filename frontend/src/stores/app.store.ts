import { defineStore } from "pinia";

import { apiFetch, setToken } from "@/composables/useApi";
import type {
  CandidateOrder,
  CostBreakdown,
  CuttingPlan,
  FeasibilityResult,
  KnifeModel,
  Material,
  Order,
  ProductionOverview,
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

    async fetchProductionOverview() {
      return apiFetch<ProductionOverview>("/admin/production/overview");
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
