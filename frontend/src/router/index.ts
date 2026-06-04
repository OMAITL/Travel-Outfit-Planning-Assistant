import { createRouter, createWebHistory } from "vue-router";
import PlanningView from "@/views/PlanningView.vue";
import TryonView from "@/views/TryonView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "planning", component: PlanningView },
    { path: "/tryon", name: "tryon", component: TryonView },
  ],
});

export default router;
