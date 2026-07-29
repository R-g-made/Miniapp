import { createRouter, createWebHashHistory } from 'vue-router';
import Dashboard from '../views/Dashboard.vue';
import StickerPool from '../views/StickerPool.vue';
import PlayerManagement from '../views/PlayerManagement.vue';
import CaseConstructor from '../views/CaseConstructor.vue';
import Broadcast from '../views/Broadcast.vue';
import Login from '../views/Login.vue';

const routes = [
    { path: '/login', component: Login, meta: { public: true } },
    { path: '/', component: Dashboard },
    { path: '/stickers', component: StickerPool },
    { path: '/players', component: PlayerManagement },
    { path: '/cases', component: CaseConstructor },
    { path: '/broadcast', component: Broadcast },
];

const router = createRouter({
    history: createWebHashHistory(),
    routes,
});

router.beforeEach((to, from, next) => {
    const token = localStorage.getItem('admin_token');
    if (!to.meta.public && !token) {
        next('/login');
    } else {
        next();
    }
});

export default router;
