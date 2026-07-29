import axios from 'axios';

const api = axios.create({
    baseURL: '/api/v1/admin',
});

api.interceptors.request.use(config => {
    const token = localStorage.getItem('admin_token');
    if (token) {
        config.headers['X-Admin-Token'] = token;
    }
    return config;
});

api.interceptors.response.use(
    response => response,
    error => {
        if (error.response && (error.response.status === 401 || error.response.status === 403)) {
            localStorage.removeItem('admin_token');
            window.location.hash = '#/login';
        }
        return Promise.reject(error);
    }
);

export default {
    login(password) {
        return api.post('/login', { password });
    },
    getDashboardStats(params) {
        return api.get('/stats/dashboard', { params });
    },
    getTopDrops(params) {
        return api.get('/stats/top-drops', { params });
    },
    getStickerPool(search) {
        return api.get('/stickers/pool', { params: { search } });
    },
    changeStickerOwner(stickerId, newOwnerId) {
        return api.patch(`/stickers/${stickerId}/owner`, { new_owner_id: newOwnerId });
    },
    getUsers(search) {
        return api.get('/users', { params: { search } });
    },
    resetUserBalance(userId) {
        return api.post(`/users/${userId}/reset-balance`);
    },
    adjustUserBalance(userId, ton, stars) {
        return api.post(`/users/${userId}/adjust-balance`, null, {
            params: { amount_ton: ton, amount_stars: stars }
        });
    },
    getCatalogItems() {
        return api.get('/catalog/items');
    },
    createCase(caseData) {
        return api.post('/cases', caseData);
    },
    createCatalogSticker(stickerData) {
        return api.post('/catalog/stickers', stickerData);
    },
    startBroadcast(broadcastData) {
        return api.post('/bot/broadcast', broadcastData);
    }
};
