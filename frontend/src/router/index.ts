import { createRouter, createWebHistory } from "vue-router";
import PlanningView from "@/views/PlanningView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [{ path: "/", name: "planning", component: PlanningView }],
});

export default router;
