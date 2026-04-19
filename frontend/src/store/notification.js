import { defineStore } from 'pinia';

export const useNotificationStore = defineStore('notification', {
    state: () => ({
        notifications: []
    }),
    actions: {
        addNotification(notification) {
            const id = Date.now() + Math.random();
            const newNotification = {
                id,
                type: notification.type || 'info', // 'success', 'error', 'info'
                title: notification.title || '',
                message: notification.message || '',
                duration: notification.duration || 5000
            };
            
            this.notifications.push(newNotification);

            if (newNotification.duration > 0) {
                setTimeout(() => {
                    this.removeNotification(id);
                }, newNotification.duration);
            }
            
            return id;
        },
        
        success(title, message, duration = 5000) {
            return this.addNotification({ type: 'success', title, message, duration });
        },
        
        error(title, message, duration = 7000) {
            return this.addNotification({ type: 'error', title, message, duration });
        },
        
        info(title, message, duration = 5000) {
            return this.addNotification({ type: 'info', title, message, duration });
        },

        removeNotification(id) {
            const index = this.notifications.findIndex(n => n.id === id);
            if (index !== -1) {
                this.notifications.splice(index, 1);
            }
        }
    }
});
