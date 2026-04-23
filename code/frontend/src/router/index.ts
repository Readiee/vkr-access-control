import { createRouter, createWebHistory } from 'vue-router';
import AppLayout from '@/layout/AppLayout.vue';

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'rules',
          component: () => import('@/views/Dashboard.vue')
        },
        {
          path: 'sandbox',
          name: 'sandbox',
          component: () => import('@/views/Sandbox.vue')
        },
        {
          path: 'verify',
          name: 'verify',
          component: () => import('@/views/VerificationReport.vue')
        }
      ]
    }
  ]
});

export default router;
