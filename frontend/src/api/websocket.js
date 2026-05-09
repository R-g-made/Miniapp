import { useAuthStore } from '../store/auth';
import { useAppStore } from '../store/app';
import { useNotificationStore } from '../store/notification';

class WebSocketService {
    constructor() {
        this.socket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        
        // Динамическое определение URL для WebSocket на основе текущего протокола страницы
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        
        // Мы всегда подключаемся к /ws/events на текущем хосте.
        // Nginx сам перенаправит это на бэкенд /api/v1/ws/events
        this.url = `${protocol}//${host}/ws/events`;
    }

    connect() {
        const authStore = useAuthStore();
        if (!authStore.token) {
            console.error("Cannot connect to WS: No token found");
            return;
        }

        // Передаем токен в query параметре, так как заголовки в стандартном WebSocket API не поддерживаются
        const wsUrl = `${this.url}?token=${authStore.token}`;
        this.socket = new WebSocket(wsUrl);

        this.socket.onopen = () => {
            console.log("WebSocket Connected");
            this.reconnectAttempts = 0;
        };

        this.socket.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                this.handleMessage(message);
            } catch (e) {
                console.error("Error parsing WS message:", e);
            }
        };

        this.socket.onclose = () => {
            console.log("WebSocket Disconnected");
            this.attemptReconnect();
        };

        this.socket.onerror = (error) => {
            console.error("WebSocket Error:", error);
        };
    }

    handleMessage(message) {
        const authStore = useAuthStore();
        const appStore = useAppStore();
        const notificationStore = useNotificationStore();
        
        switch (message.type) {
            case 'live_drop':
                appStore.addLiveDrop(message.data);
                break;
            case 'balance_update':
                authStore.updateBalance(message.data.new_balance, message.data.currency);
                notificationStore.success('Success', `Balance Updated`);
                break;
            case 'sticker_received':
                notificationStore.success('Success', `You received: ${message.data.name}`);
                // Можно добавить обновление инвентаря если есть такой метод
                break;
            case 'transaction_completed':
                notificationStore.success('Success', `Transaction completed`);
                break;
            case 'transaction_failed':
                notificationStore.error('Failed', message.data.error || 'Unknown error');
                break;
            case 'user_event':
                if (message.event_type === 'balance_update') {
                    authStore.updateBalance(message.data.new_balance, message.data.currency);
                    notificationStore.success('Success', `Balance Updated`);
                }
                break;
            case 'error':
                notificationStore.error('Failed', message.data.message || 'Something went wrong');
                break;
            case 'case_status_update':
                appStore.updateCaseStatus(
                    message.data.case_slug,
                    message.data.is_active,
                    message.data.price_ton,
                    message.data.price_stars
                );
                // Отправляем кастомное событие для CaseView
                window.dispatchEvent(new CustomEvent('ws:case_status_update', {
                    detail: message.data
                }));
                break;
            case 'global_event':
                console.log("Global Event:", message.data);
                if (message.data.message) {
                    notificationStore.info('Announcement', message.data.message);
                }
                break;
        }
    }

    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 10000);
            console.log(`Attempting reconnect in ${delay}ms...`);
            setTimeout(() => this.connect(), delay);
        }
    }

    disconnect() {
        if (this.socket) {
            this.socket.close();
        }
    }
}

export const wsService = new WebSocketService();
