import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "home",
      component: () => import("../components/ResearchHome.vue"),
    },
    {
      path: "/research/:id?",
      name: "research",
      component: () => import("../components/ResearchDetail.vue"),
    },
    {
      path: "/history",
      name: "history",
      component: () => import("../components/ResearchHistory.vue"),
    },
  ],
});

export default router;
