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
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '../store/auth';
import { useNotificationStore } from '../store/notification';

export default {
  name: 'ProfileView',
  setup() {
    const router = useRouter();
    const authStore = useAuthStore();
    const notificationStore = useNotificationStore();
    
    const currentLang = ref('en');

    const user = computed(() => {
        // Пробуем взять из стора или напрямую из Telegram WebApp
        return authStore.user || window.Telegram?.WebApp?.initDataUnsafe?.user || {
            first_name: 'Real',
            last_name: 'glory'
        };
    });

    const fullName = computed(() => {
      const first = user.value?.first_name || '';
      const last = user.value?.last_name || '';
      return `${first} ${last}`.trim();
    });

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
      window.Telegram?.WebApp?.openTelegramLink('https://t.me/support_bot');
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
      openReferrals
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
