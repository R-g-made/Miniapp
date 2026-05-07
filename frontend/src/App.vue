<template>
  <div class="app-container">
    <header class="app-header">
      <BalanceBar @add-funds="openDeposit" />
    </header>
    <main class="app-content">
      <router-view></router-view>
    </main>
    <NavBar />
    <DepositModal />
    <NotificationContainer />
  </div>
</template>

<script>
import { watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from './store/auth';
import { useAppStore } from './store/app';
import { wsService } from './api/websocket';
import BalanceBar from './components/BalanceBar.vue';
import NavBar from './components/NavBar.vue';
import DepositModal from './components/DepositModal.vue';
import NotificationContainer from './components/NotificationContainer.vue';

export default {
  components: { BalanceBar, NavBar, DepositModal, NotificationContainer },
  setup() {
    const authStore = useAuthStore();
    const appStore = useAppStore();
    const router = useRouter();
    const route = useRoute();

    // Обработка кнопки "Назад" в Telegram
    const setupBackButton = () => {
      const tg = window.Telegram?.WebApp;
      if (!tg) return;

      const backButton = tg.BackButton;

      watch(() => route.path, (newPath) => {
        if (newPath === '/' || newPath === '/home') {
          backButton.hide();
        } else {
          backButton.show();
        }
      });

      backButton.onClick(() => {
        router.back();
      });
    };

    setupBackButton();

    const openDeposit = () => {
      appStore.setDepositOpen(true);
    };

    return { authStore, appStore, openDeposit };
  },
  async mounted() {
    await this.authStore.initialize();
    await this.appStore.fetchBootstrap();
    
    // Подключаемся к WebSocket после авторизации
    if (this.authStore.isLoggedIn) {
      wsService.connect();
    }
    
    // Запрашиваем полноэкранный режим
    if (window.Telegram?.WebApp) {
      if (window.Telegram.WebApp.requestFullscreen) {
        window.Telegram.WebApp.requestFullscreen();
      } else if (window.Telegram.WebApp.expand) {
        window.Telegram.WebApp.expand();
      }
    }
  },
  unmounted() {
    wsService.disconnect();
  }
}
</script>

<style>
* {
  -webkit-tap-highlight-color: transparent;
  -webkit-touch-callout: none;
  -webkit-user-select: none;
  -khtml-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
  user-select: none;
  outline: none;
}

input, textarea {
  -webkit-user-select: text;
  -khtml-user-select: text;
  -moz-user-select: text;
  -ms-user-select: text;
  user-select: text;
}

body {
  margin: 0;
  background-color: #171717;
}

.app-container {
  display: flex;
  flex-direction: column;
  padding: calc(65px + env(safe-area-inset-top, 0px)) 0 100px 0;
  gap: 10px; /* Гэп 10px */
}

.app-header, .app-content {
  padding-left: 20px;
  padding-right: 20px;
}

.app-header {
  display: flex;
  justify-content: flex-end;
}
</style>
