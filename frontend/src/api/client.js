import axios from 'axios';
import { useNotificationStore } from '../store/notification';

const apiClient = axios.create({
    baseURL: import.meta.env.VITE_API_URL || '/api/v1',
    headers: {
        'Content-Type': 'application/json',
    }
});

// Перехватчик для автоматической распаковки SuccessResponse
apiClient.interceptors.response.use(
    (response) => {
        // Если бэкенд вернул SuccessResponse, вытаскиваем данные из поля data
        if (response.data && response.data.status === 'success' && response.data.data !== undefined) {
            return { ...response, data: response.data.data };
        }
        return response;
    },
    (error) => {
        const notificationStore = useNotificationStore();
        
        if (error.response) {
            const data = error.response.data;
            const message = data.message || error.message;
            const code = data.code || `Error ${error.response.status}`;
            
            notificationStore.error(code, message);
        } else if (error.request) {
            notificationStore.error('Network Error', 'No response from server');
        } else {
            notificationStore.error('Error', error.message);
        }
        
        return Promise.reject(error);
    }
);

// Функция для динамической установки токена
export const setAuthToken = (token) => {
    if (token) {
        apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    } else {
        delete apiClient.defaults.headers.common['Authorization'];
    }
};

export default {
    // Auth
    login: (initData) => apiClient.post('/auth', { init_data: initData }),
    
    // Core
    getBootstrap: () => apiClient.get('/bootstrap'),

    // Cases
    getCases: (params) => apiClient.get('/cases', { params }),
    getCase: (slug) => apiClient.get(`/cases/${slug}`),
    openCase: (slug, currency) => apiClient.post(`/cases/${slug}/open`, { currency }),

    // Stickers
    getMyStickers: (params) => apiClient.get('/stickers/my', { params }),
    sellSticker: (uuid, currency) => apiClient.post(`/stickers/${uuid}/sell`, { currency }),
    transferSticker: (uuid) => apiClient.post(`/stickers/${uuid}/transfer`, {}),

    // Referrals
    getReferralStats: () => apiClient.get('/referrals/stats'),
    withdrawReferrals: (data) => apiClient.post('/referrals/withdraw', data),

    // Wallet
    getTonProofPayload: () => apiClient.get('/wallet/ton-proof/payload'),
    checkTonProof: (proofData) => apiClient.post('/wallet/ton-proof/check', proofData),
    replenishWallet: (data) => apiClient.post('/wallet/replenish', data),
    withdrawWallet: (data) => apiClient.post('/wallet/withdraw', data),
};
