import { createRouter, createWebHistory } from "vue-router";

import { apiFetch, hasToken } from "@/composables/useApi";
import type { ShopSettings } from "@/types";

const routes = [
  { path: "/login", name: "login", component: () => import("@/pages/admin/LoginPage.vue") },
  {
    path: "/",
    name: "materials",
    component: () => import("@/pages/admin/MaterialsPage.vue"),
    meta: { requiresAdmin: true },
  },
  {
    path: "/treatments",
    name: "treatments",
    component: () => import("@/pages/admin/TreatmentsPage.vue"),
    meta: { requiresAdmin: true },
  },
  {
    path: "/knife-models",
    name: "knife-models",
    component: () => import("@/pages/admin/KnifeModelsPage.vue"),
    meta: { requiresAdmin: true },
  },
  {
    path: "/knife-models/:id",
    name: "knife-model-detail",
    component: () => import("@/pages/admin/KnifeModelDetailPage.vue"),
    meta: { requiresAdmin: true },
  },
  {
    path: "/production",
    name: "production",
    component: () => import("@/pages/admin/ProductionPage.vue"),
    meta: { requiresAdmin: true },
  },
  {
    path: "/orders",
    name: "orders",
    component: () => import("@/pages/admin/OrdersPage.vue"),
    meta: { requiresAdmin: true },
  },
  {
    path: "/orders/:id",
    name: "order-detail",
    component: () => import("@/pages/admin/OrderDetailPage.vue"),
    meta: { requiresAdmin: true },
  },
  {
    path: "/designs",
    name: "designs",
    component: () => import("@/pages/admin/DesignsPage.vue"),
    meta: { requiresAdmin: true },
  },
  {
    path: "/designs/:id",
    name: "design-editor",
    component: () => import("@/pages/admin/DesignEditorPage.vue"),
    meta: { requiresAdmin: true },
  },
  {
    path: "/nesting",
    name: "nesting",
    component: () => import("@/pages/admin/NestingPage.vue"),
    meta: { requiresAdmin: true },
  },
  {
    path: "/bienvenue",
    name: "welcome",
    component: () => import("@/pages/admin/WelcomePage.vue"),
    meta: { requiresAdmin: true },
  },
  {
    path: "/settings",
    name: "settings",
    component: () => import("@/pages/admin/SettingsPage.vue"),
    meta: { requiresAdmin: true },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

// first-run wizard: checked once per page load, after sign-in
let onboardingChecked = false;

router.beforeEach(async (to) => {
  if (to.meta.requiresAdmin && !hasToken()) {
    return { name: "login" };
  }
  if (to.meta.requiresAdmin && !onboardingChecked && to.name !== "welcome") {
    onboardingChecked = true;
    try {
      const shop = await apiFetch<ShopSettings>("/admin/settings/shop");
      if (!shop.onboarding_done) return { name: "welcome" };
    } catch {
      // the page itself will report the API problem
    }
  }
});

export default router;
