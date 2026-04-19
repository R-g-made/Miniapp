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

export default router
