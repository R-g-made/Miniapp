<template>
  <div class="app-container">
    <template v-if="!appStore.isMaintenance">
      <header class="app-header">
        <BalanceBar @add-funds="openDeposit" />
      </header>
      <main class="app-content">
        <router-view></router-view>
      </main>
      <NavBar />
      <DepositModal />
      <SubscribeModal />
      <NotificationContainer />
    </template>
    <MaintenanceView v-else />
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
import SubscribeModal from './components/SubscribeModal.vue';
import NotificationContainer from './components/NotificationContainer.vue';
import MaintenanceView from './components/MaintenanceView.vue';

export default {
  components: { BalanceBar, NavBar, DepositModal, SubscribeModal, NotificationContainer, MaintenanceView },
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
        // Скрываем кнопку назад на страницах, где есть нижняя навигация
        if (newPath === '/' || newPath === '/home' || newPath === '/inventory' || newPath === '/profile' || newPath === '/tournament') {
          backButton.hide();
        } else {
          backButton.show();
        }
      });

      backButton.onClick(() => {
        // Возврат на ближайшую страницу с навбаром
        if (route.path.startsWith('/case/')) {
          router.push('/');
        } else if (route.path === '/referrals') {
          router.push('/profile');
        } else {
          router.back();
        }
      });
    };

    setupBackButton();

    const openDeposit = () => {
      appStore.setDepositOpen(true);
    };

    // Глобальная проверка сессии кошелька при загрузке приложения
    const checkWalletSession = async () => {
      try {
        if (authStore.user?.wallet_address) {
          const { getTonConnect, disconnectWallet } = await import('./api/tonConnect');
          const tc = await getTonConnect();
          
          // Если TonConnect говорит что отключен, а в БД есть кошелек
          if (!tc.connected) {
            console.log('App: TonConnect session expired, cleaning up...');
            
            // Вызываем notification
            // const notificationStore = (await import('./store/notification')).useNotificationStore();
            // notificationStore.info('Session expired', 'Please reconnect your wallet to continue');
            
            // Очищаем локально и на бэкенде
            try {
              await disconnectWallet();
              const api = (await import('./api/client')).default;
              await api.disconnectWallet();
            } catch (err) {
              console.error('App: Error while auto-disconnecting:', err);
            }
            
            // Очищаем стор
            if (authStore.user) {
              authStore.user.wallet_address = null;
            }
          }
        }
      } catch (e) {
        console.error('App: Error checking wallet session', e);
      }
    };

    return { authStore, appStore, openDeposit, checkWalletSession };
  },
  mounted() {
    this.checkWalletSession();

    const checkFullscreen = () => {
      if (!window.Telegram?.WebApp) return;
      
      const platform = window.Telegram.WebApp.platform;
      const desktopPlatforms = ['macos', 'tdesktop', 'web', 'weba', 'desktop'];
      
      if (desktopPlatforms.includes(platform) || window.innerWidth > 600) {
        // На десктопе или планшетах не запрашиваем Fullscreen. Если есть метод выхода - вызываем.
        if (window.Telegram.WebApp.exitFullscreen) {
          try {
            window.Telegram.WebApp.exitFullscreen();
          } catch (e) {}
        }
      } else {
        // Запрашиваем полноэкранный режим только для мобильных (ширина <= 600)
        if (window.Telegram.WebApp.requestFullscreen) {
          try {
            window.Telegram.WebApp.requestFullscreen();
          } catch (e) {}
        } else if (window.Telegram.WebApp.expand) {
          try {
            window.Telegram.WebApp.expand();
          } catch (e) {}
        }
      }
    };

    checkFullscreen();
    window.addEventListener('resize', checkFullscreen);
    this._checkFullscreen = checkFullscreen;
  },
  unmounted() {
    if (this._checkFullscreen) {
      window.removeEventListener('resize', this._checkFullscreen);
    }
    import('./api/websocket').then(({ wsService }) => {
      wsService.disconnect();
    });
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

/* Увеличиваем иконку звезды (STARS) глобально во всем приложении */
img[src*="star"] {
  transform: scale(1.3);
}
</style>
