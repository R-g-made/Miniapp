<template>
  <div class="profile-view">
    <!-- Секция аватара и имени -->
    <div class="profile-header">
      <div class="avatar-container">
        <img v-if="userPhoto" :src="userPhoto" alt="Avatar" class="avatar-img">
        <div v-else class="avatar-placeholder">
          {{ userInitials }}
        </div>
      </div>
      <h1 class="user-name">{{ fullName }}</h1>

      <!-- Wallet Section -->
      <div class="wallet-section" v-click-outside="closeMenu">
        <div class="wallet-btn" @click="handleWalletClick">
          <svg viewBox="0 0 22.8441 18.594" xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none">
            <g opacity="1">
              <path d="M5.04694 5.04688L9.29699 5.04688" stroke="#007AFF" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.593768" />
              <path d="M18.0425 6.10938C16.146 6.10938 14.6096 7.53633 14.6096 9.29691C14.6096 11.0575 16.147 12.4844 18.0415 12.4844L20.8072 12.4844C20.8964 12.4844 20.94 12.4844 20.9772 12.4823C21.551 12.4473 22.0078 12.0233 22.045 11.491C22.0471 11.457 22.0471 11.4156 22.0471 11.3337L22.0471 7.26008C22.0471 7.17826 22.0471 7.13682 22.045 7.10282C22.0068 6.57051 21.5509 6.14656 20.9772 6.1115C20.9411 6.10938 20.8975 6.10938 20.8083 6.10938L20.8072 6.10938L18.0425 6.10938Z" fill-rule="nonzero" stroke="#007AFF" stroke-width="1.593768" />
              <path d="M20.9474 6.10944C20.8645 4.12041 20.5989 2.90065 19.7393 2.04214C18.4951 0.796875 16.4912 0.796875 12.4845 0.796875L9.29697 0.796875C5.29024 0.796875 3.28634 0.796875 2.04214 2.04214C0.797937 3.2874 0.796875 5.29024 0.796875 9.29697C0.796875 13.3037 0.796875 15.3076 2.04214 16.5518C3.2874 17.796 5.29024 17.7971 9.29697 17.7971L12.4845 17.7971C16.4912 17.7971 18.4951 17.7971 19.7393 16.5518C20.5989 15.6933 20.8656 14.4735 20.9474 12.4845" fill-rule="nonzero" stroke="#007AFF" stroke-width="1.593768" />
              <path d="M17.7875 9.29688L17.7981 9.29688" stroke="#007AFF" stroke-linecap="round" stroke-linejoin="round" stroke-width="2.125025" />
            </g>
          </svg>
          <span v-if="!isConnected" class="wallet-text">Connect Wallet</span>
          <span v-else class="wallet-text">{{ shortAddress }}</span>
        </div>
        
        <!-- Dropdown Menu -->
        <Transition name="fade">
          <div v-if="isMenuOpen" class="wallet-menu" @click.stop>
            <div class="menu-item" @click="openTopUp">
              <span class="menu-text">Top Up</span>
              <img src="@/assets/icons/plus.svg" class="menu-icon plus-icon" />
            </div>
            <div class="menu-item disconnect" @click="disconnect">
              <span class="menu-text disconnect-text">Disconnect</span>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="menu-icon">
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" stroke="#FF3B30" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" stroke="#FF3B30" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <line x1="8" y1="16" x2="16" y2="8" stroke="#FF3B30" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
          </div>
        </Transition>
      </div>
    </div>

    <!-- Основной блок настроек -->
    <div class="settings-card">
      <!-- Язык -->
      <div class="settings-item">
        <div class="item-left">
          <img src="@/assets/icons/world.svg" alt="Language" class="item-icon">
          <span class="item-text">Language</span>
        </div>
        <div class="language-selector" @click="toggleLanguage">
          <div class="selector-bg">
            <div class="selector-thumb" :class="{ 'is-ru': currentLang === 'ru' }"></div>
            <span class="lang-option" :class="{ active: currentLang === 'en' }">EN</span>
            <span class="lang-option" :class="{ active: currentLang === 'ru' }">РУ</span>
          </div>
        </div>
      </div>

      <!-- Разделитель (визуальный отступ между айтемами 27px) -->
      <div class="settings-divider"></div>

      <!-- Поддержка -->
      <div class="settings-item clickable" @click="openSupport">
        <div class="item-left">
          <img src="@/assets/icons/support.svg" alt="Support" class="item-icon">
          <span class="item-text">Support</span>
        </div>
        <img src="@/assets/icons/arrow.svg" alt="Arrow" class="arrow-icon">
      </div>
    </div>

    <!-- Блок реферальной программы (отступ 30px) -->
    <div class="referral-card clickable" @click="openReferrals">
      <div class="item-left">
        <img src="@/assets/icons/share.svg" alt="Referral" class="item-icon">
        <span class="item-text">Referral program</span>
      </div>
      <img src="@/assets/icons/arrow.svg" alt="Arrow" class="arrow-icon">
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '../store/auth';
import { useAppStore } from '../store/app';
import { useNotificationStore } from '../store/notification';
import { toUserFriendlyAddress } from '@tonconnect/ui';

// Simple click-outside directive
const vClickOutside = {
  mounted(el, binding) {
    el.clickOutsideEvent = function(event) {
      if (!(el === event.target || el.contains(event.target))) {
        binding.value(event);
      }
    };
    document.body.addEventListener('click', el.clickOutsideEvent);
  },
  unmounted(el) {
    document.body.removeEventListener('click', el.clickOutsideEvent);
  }
};

export default {
  name: 'ProfileView',
  directives: {
    clickOutside: vClickOutside
  },
  setup() {
    const router = useRouter();
    const authStore = useAuthStore();
    const appStore = useAppStore();
    const notificationStore = useNotificationStore();
    
    const currentLang = ref('en');
    
    // Инициализируем из стора, чтобы не было "прыжка" при загрузке
    const isConnected = ref(!!authStore.user?.wallet_address);
    const walletAddress = ref(authStore.user?.wallet_address || '');

    // Следим за изменениями в authStore, чтобы подхватывать кошелек из БД
    watch(() => authStore.user?.wallet_address, (newAddr) => {
      if (newAddr) {
        isConnected.value = true;
        walletAddress.value = newAddr;
      } else if (!authStore.isLoading) {
        // Если в БД пусто, проверяем TonConnect, прежде чем сбрасывать
        import('../api/tonConnect').then(async ({ getTonConnect }) => {
          const tc = await getTonConnect();
          if (!tc.connected) {
            isConnected.value = false;
            walletAddress.value = '';
          }
        });
      }
    });
    
    const isMenuOpen = ref(false);
    let unsubscribe = null;

    onMounted(async () => {
      // 1. Сначала проверяем статус через библиотеку
      try {
        const { getTonConnect } = await import('../api/tonConnect');
        const tc = await getTonConnect();
        
        if (tc.connected && tc.account) {
          isConnected.value = true;
          walletAddress.value = tc.account.address;
        } else if (authStore.user?.wallet_address) {
          // Если библиотека говорит "не подключен", но в БД есть адрес - 
          // доверяем БД для отображения, пока юзер не нажмет Disconnect
          isConnected.value = true;
          walletAddress.value = authStore.user.wallet_address;
        }
        
        unsubscribe = tc.onStatusChange((wallet) => {
          if (wallet) {
            isConnected.value = true;
            walletAddress.value = wallet.account.address;
          } else {
            // Если в БД всё еще есть адрес, не сбрасываем отображение сразу, 
            // чтобы не дергать интерфейс при мимолетных дисконнектах
            if (!authStore.user?.wallet_address) {
              isConnected.value = false;
              walletAddress.value = '';
              isMenuOpen.value = false;
            }
          }
        });
      } catch (e) {
        console.error('Failed to init ton connect in profile', e);
      }
    });

    onUnmounted(() => {
      if (unsubscribe) unsubscribe();
    });

    const user = computed(() => {
        return authStore.user || window.Telegram?.WebApp?.initDataUnsafe?.user || {
            first_name: 'User'
        };
    });

    const fullName = computed(() => {
      if (authStore.user?.full_name) return authStore.user.full_name;
      const first = user.value?.first_name || '';
      const last = user.value?.last_name || '';
      return `${first} ${last}`.trim() || 'User';
    });

    const shortAddress = computed(() => {
      if (!walletAddress.value) return '';
      try {
        // Преобразуем сырой адрес (0:...) в читаемый (UQ...)
        const friendlyAddr = toUserFriendlyAddress(walletAddress.value);
        return `${friendlyAddr.slice(0, 4)}...${friendlyAddr.slice(-4)}`;
      } catch (e) {
        // Если это уже дружественный адрес или произошла ошибка
        const addr = walletAddress.value;
        return `${addr.slice(0, 4)}...${addr.slice(-4)}`;
      }
    });

    const handleWalletClick = async () => {
      if (isConnected.value) {
        isMenuOpen.value = !isMenuOpen.value;
      } else {
        const { connectWallet } = await import('../api/tonConnect');
        connectWallet();
      }
    };

    const openTopUp = () => {
      isMenuOpen.value = false;
      appStore.setDepositOpen(true);
    };

    const disconnect = async () => {
      isMenuOpen.value = false;
      try {
        const { disconnectWallet } = await import('../api/tonConnect');
        await disconnectWallet();
        
        // Also call backend disconnect API if available
        const api = (await import('../api/client')).default;
        await api.disconnectWallet();

        // Обновляем стор
        if (authStore.user) {
          authStore.user.wallet_address = null;
        }
        
        isConnected.value = false;
        walletAddress.value = '';
      } catch (e) {
        console.error('Disconnect error', e);
      }
    };

    const closeMenu = () => {
      isMenuOpen.value = false;
    };

    const userInitials = computed(() => {
      const first = user.value?.first_name?.charAt(0) || '';
      const last = user.value?.last_name?.charAt(0) || '';
      return (first + last).toUpperCase();
    });

    const userPhoto = computed(() => {
      return user.value?.photo_url || null;
    });

    const toggleLanguage = () => {
      if (currentLang.value === 'en') {
        currentLang.value = 'ru';
        notificationStore.info('Soon', 'Language change will be available soon');
        setTimeout(() => {
          currentLang.value = 'en';
        }, 300);
      }
    };

    const openSupport = () => {
      // Логика открытия поддержки (например ссылка на бота)
      window.Telegram?.WebApp?.openTelegramLink('https://t.me/stickerloot_support');
    };

    const openReferrals = () => {
      router.push({ name: 'Referrals' });
    };

    return {
      user,
      fullName,
      userInitials,
      userPhoto,
      currentLang,
      toggleLanguage,
      openSupport,
      openReferrals,
      isConnected,
      walletAddress,
      shortAddress,
      isMenuOpen,
      handleWalletClick,
      openTopUp,
      disconnect,
      closeMenu
    };
  }
}
</script>

<style scoped>
.profile-view {
  padding: 30px 0; /* Только вертикальный паддинг */
  display: flex;
  flex-direction: column;
  align-items: center;
}

.profile-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 30px;
  padding: 0 20px; /* Боковые отступы для хедера */
}

.avatar-container {
  width: 88px;
  height: 88px;
  border-radius: 50%;
  overflow: hidden;
  margin-bottom: 24px;
  background: linear-gradient(135deg, #2b70c9 0%, #33a1de 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-placeholder {
  font-size: 32px;
  font-weight: 700;
  color: #FFFFFF;
}

.user-name {
  font-size: 23px;
  font-weight: 600;
  color: #FFFFFF;
  margin: 0;
  text-align: center;
}

.wallet-section {
  position: relative;
  margin-top: 8px;
}

.wallet-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 8px;
  transition: opacity 0.2s;
}

.wallet-btn:active {
  opacity: 0.7;
}

.wallet-icon {
  width: 16px;
  height: 16px;
  filter: invert(31%) sepia(94%) border-left(100%) saturate(2542%) hue-rotate(201deg) brightness(101%) contrast(105%);
}

.wallet-text {
  font-size: 15px;
  font-weight: 500;
  color: #007AFF;
}

.wallet-menu {
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  margin-top: 8px;
  background: rgba(32, 32, 32, 0.1);
  backdrop-filter: blur(50px);
  -webkit-backdrop-filter: blur(50px);
  border-radius: 20px;
  padding: 8px;
  width: 160px;
  z-index: 100;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.menu-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.2s;
}

.menu-item:active {
  background: rgba(255,255,255,0.1);
}

.menu-text {
  font-size: 15px;
  font-weight: 500;
  color: #FFFFFF;
}

.disconnect-text {
  color: #FF3B30;
}

.menu-icon {
  width: 18px;
  height: 18px;
}

.plus-icon {
  transform: scale(0.9);
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
  transform: translate(-50%, -10px);
}

.settings-card {
  width: 100%;
  background-color: #202020;
  border-radius: 33px; /* Закругление 33 */
  padding: 20px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  margin-bottom: 30px;
}

.settings-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.referral-card {
  width: 100%;
  background-color: #202020;
  border-radius: 27px; /* Закругление 27 */
  padding: 25px 20px; /* Паддинг 25 по вертикали, 20 по горизонтали */
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.referral-card {
  margin-bottom: 0;
}

.clickable {
  cursor: pointer;
  transition: opacity 0.2s;
}

.clickable:active {
  opacity: 0.7;
}

.item-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.item-icon {
  width: 19px;
  height: 19px;
  object-fit: contain;
}

.item-text {
  font-size: 17px;
  font-weight: 600;
  color: #FFFFFF;
}

.settings-divider {
  height: 27px;
}

.arrow-icon {
  width: 14px;
  height: 14px;
  object-fit: contain;
  opacity: 0.5;
}

/* Языковой селектор (слайдер) */
.language-selector {
  cursor: pointer;
}

.selector-bg {
  width: 86px;
  height: 32px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 1000px;
  position: relative;
  display: flex;
  align-items: center;
  padding: 2px;
  box-sizing: border-box;
}

.selector-thumb {
  position: absolute;
  width: 40px;
  height: 28px;
  background: #FFFFFF;
  border-radius: 1000px;
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 1;
}

.selector-thumb.is-ru {
  transform: translateX(42px);
}

.lang-option {
  flex: 1;
  text-align: center;
  font-size: 14px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.5);
  z-index: 2;
  transition: color 0.3s;
}

.lang-option.active {
  color: #000000;
}
</style>
