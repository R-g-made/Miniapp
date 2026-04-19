import { defineStore } from 'pinia';
import api, { setAuthToken } from '../api/client';

export const useAuthStore = defineStore('auth', {
    state: () => ({
        user: null,
        token: null,
        tonProofPayload: null,
        initialized: false,
        isLoading: false
    }),
    
    getters: {
        isLoggedIn: (state) => !!state.token && !!state.user,
        balanceTon: (state) => state.user?.balance_ton || 0,
        balanceStars: (state) => state.user?.balance_stars || 0,
    },
    
    actions: {
        async initialize() {
            this.isLoading = true;
            try {
                // Если мы в Telegram, используем реальные данные, иначе мокаем ID для веба
                let initData = window.Telegram?.WebApp?.initData;
                
                if (!initData) {
                    // Для локальной разработки без TG: создаем моковый initData с ID 12345678
                    const mockUser = JSON.stringify({
                        id: 12345678,
                        first_name: "Test",
                        last_name: "User",
                        username: "testuser",
                        language_code: "en"
                    });
                    initData = `user=${encodeURIComponent(mockUser)}&hash=mock_hash`;
                }
                
                const response = await api.login(initData);
                
                if (response.data.access_token) {
                    this.token = response.data.access_token;
                    this.user = response.data.user;
                    this.tonProofPayload = response.data.ton_proof_payload;
                    
                    // Устанавливаем токен в заголовки API
                    setAuthToken(this.token);
                    
                    this.initialized = true;
                    this.isLoading = false;
                    return true;
                }
                return false;
            } catch (error) {
                console.error("Authentication failed:", error);
                this.isLoading = false;
                return false;
            }
        },
        
        updateBalance(newBalance, currency) {
            if (!this.user) return;
            const key = `balance_${currency.toLowerCase()}`;
            if (Object.prototype.hasOwnProperty.call(this.user, key)) {
                this.user[key] = newBalance;
            }
        },
        
        logout() {
            this.user = null;
            this.token = null;
            setAuthToken(null);
        }
    }
});
