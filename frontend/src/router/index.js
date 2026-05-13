import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Inventory from '../views/Inventory.vue'
import CaseView from '../views/CaseView.vue'
import Profile from '../views/Profile.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home
  },
  {
    path: '/case/:slug',
    name: 'CaseView',
    component: CaseView
  },
  {
    path: '/inventory',
    name: 'Inventory',
    component: Inventory
  },
  {
    path: '/profile',
    name: 'Profile',
    component: Profile
  },
  {
    path: '/referrals',
    name: 'Referrals',
    component: () => import('../views/Referrals.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to, from, next) => {
  const { useAuthStore } = await import('../store/auth');
  const { useAppStore } = await import('../store/app');
  const { wsService } = await import('../api/websocket');
  
  const authStore = useAuthStore();
  const appStore = useAppStore();

  // Если приложение еще не инициализировано, делаем это
  if (!authStore.initialized) {
    const success = await authStore.initialize();
    if (success) {
      await appStore.fetchBootstrap();
      wsService.connect();
    } else {
      // Если авторизация не удалась, можно прервать загрузку
      // или показать специальную страницу ошибки. Пока просто пускаем дальше,
      // но в реале лучше вывести экран "Не удалось авторизоваться".
    }
  }

  next();
});

export default router
