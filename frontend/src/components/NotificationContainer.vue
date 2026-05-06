<template>
  <div class="notification-container">
    <TransitionGroup name="notification-list">
      <div 
        v-for="notification in notifications" 
        :key="notification.id"
        class="notification-item"
        :class="notification.type"
      >
        <div class="notification-content">
          <div v-if="notification.title" class="notification-title">
            {{ notification.title }}
          </div>
          <div v-if="notification.message" class="notification-message">
            {{ notification.message }}
          </div>
        </div>
        <div class="notification-close" @click="remove(notification.id)">
          <i class="bi bi-x"></i>
        </div>
      </div>
    </TransitionGroup>
  </div>
</template>

<script>
import { useNotificationStore } from '../store/notification';
import { storeToRefs } from 'pinia';

export default {
  name: 'NotificationContainer',
  setup() {
    const store = useNotificationStore();
    const { notifications } = storeToRefs(store);

    const remove = (id) => {
      store.removeNotification(id);
    };

    return {
      notifications,
      remove
    };
  }
}
</script>

<style scoped>
.notification-container {
  position: fixed;
  top: calc(20px + var(--tg-content-safe-area-inset-top, var(--tg-safe-area-inset-top, env(safe-area-inset-top, 20px))));
  left: 50%;
  transform: translateX(-50%);
  width: calc(100% - 40px);
  max-width: 400px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 10px;
  pointer-events: none;
}

.notification-item {
  pointer-events: auto;
  border-radius: 1000px;
  padding: 16px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  backdrop-filter: blur(40px);
  -webkit-backdrop-filter: blur(40px);
  position: relative;
  overflow: hidden;
  box-sizing: border-box;
}

/* Ошибка: FF6D6D 20% */
.notification-item.error {
  background: rgba(255, 109, 109, 0.2);
}

/* Успех: 96FF54 20% */
.notification-item.success {
  background: rgba(150, 255, 84, 0.2);
}

/* Инфо (по умолчанию): белый 10% */
.notification-item.info {
  background: rgba(255, 255, 255, 0.1);
}

.notification-content {
  flex: 1;
}

.notification-title {
  font-weight: 600;
  font-size: 16px;
  color: #FFFFFF;
  margin-bottom: 4px;
}

.notification-message {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
}

.notification-close {
  margin-left: 12px;
  cursor: pointer;
  color: #FFFFFF;
  opacity: 0.5;
  font-size: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.notification-close:hover {
  opacity: 1;
}

/* Анимации */
.notification-list-enter-active,
.notification-list-leave-active {
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.notification-list-enter-from {
  opacity: 0;
  transform: translateY(-30px) scale(0.9);
}

.notification-list-leave-to {
  opacity: 0;
  transform: translateY(-30px) scale(0.9);
}

.notification-list-move {
  transition: transform 0.4s ease;
}
</style>
