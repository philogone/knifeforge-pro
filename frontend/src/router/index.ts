import { createRouter, createWebHistory } from "vue-router";

import { hasToken } from "@/composables/useApi";

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

router.beforeEach((to) => {
  if (to.meta.requiresAdmin && !hasToken()) {
    return { name: "login" };
  }
});

export default router;
