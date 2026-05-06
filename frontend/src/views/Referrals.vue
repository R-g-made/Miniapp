<template>
  <div class="referrals-view">
    <!-- Верхний блок Refferal program -->
    <div class="ref-promo-card" :class="{ 'is-stars': activeRefCurrency === 'STARS' }">
      <div class="ref-header">
        <img src="@/assets/icons/share.svg" alt="Share" class="ref-header-icon">
        <span class="ref-header-title">Refferal program</span>
      </div>
      
      <div class="ref-promo-text">
        <div class="promo-line">Invite friends</div>
        <div class="promo-line">
          And earn 
          <span class="percent-pill">{{ stats.ref_percentage }}%</span>
        </div>
        <div class="promo-line">their fees</div>
      </div>

      <!-- Lottie Dog -->
      <div class="lottie-container" ref="lottieContainer"></div>

      <!-- Переключатель валют (внутри синего блока) -->
      <div class="ref-currency-selector" @click="toggleCurrency">
        <div class="ref-selector-bg">
          <div class="ref-selector-thumb" :class="{ 'is-stars': activeRefCurrency === 'STARS' }"></div>
          <div class="ref-lang-option" :class="{ active: activeRefCurrency === 'TON' }">
            <img src="@/assets/icons/ton.svg" alt="TON" class="ref-curr-icon">
          </div>
          <div class="ref-lang-option" :class="{ active: activeRefCurrency === 'STARS' }">
            <img src="@/assets/icons/star.svg" alt="STARS" class="ref-curr-icon">
          </div>
        </div>
      </div>

      <!-- Блоки статистики -->
      <div class="stats-row">
        <div class="stat-box">
          <div class="stat-value-row">
            <img v-if="activeRefCurrency === 'TON'" src="@/assets/icons/ton.svg" alt="TON" class="stat-curr-icon">
            <img v-else src="@/assets/icons/star.svg" alt="STARS" class="stat-curr-icon">
            <span class="stat-number">{{ activeRefCurrency === 'TON' ? (stats.available_ton || 0) : (stats.available_stars || 0) }}</span>
          </div>
          <div class="stat-label">Totaly earned</div>
        </div>
        <div class="stat-box">
          <span class="stat-number">{{ stats.count || 0 }}</span>
          <div class="stat-label">Totaly Invited</div>
        </div>
      </div>

      <!-- 21d locked (только для Stars) -->
      <div class="locked-stars-row" v-if="activeRefCurrency === 'STARS'">
        <div class="locked-left">
          <span class="locked-label">21d locked</span>
        </div>
        <div class="locked-right">
          <img src="@/assets/icons/star.svg" alt="STARS" class="locked-curr-icon">
          <span class="locked-number">{{ stats.locked_stars || 0 }}</span>
        </div>
      </div>

      <!-- Блок вывода -->
      <div class="withdraw-box clickable" @click="handleWithdraw">
        <div class="withdraw-main">
          <div class="withdraw-left">
            <img v-if="activeRefCurrency === 'TON'" src="@/assets/icons/ton.svg" alt="TON" class="withdraw-curr-icon">
            <img v-else src="@/assets/icons/star.svg" alt="STARS" class="withdraw-curr-icon">
            <span class="withdraw-number">{{ activeRefCurrency === 'TON' ? (stats.available_ton || 0) : (stats.available_stars || 0) }}</span>
          </div>
          <div v-if="activeRefCurrency === 'STARS'" class="ton-pill">
            <img src="@/assets/icons/ton.svg" alt="TON" class="ton-pill-icon">
            <span class="ton-pill-text">{{ stats.available_in_ton || 0 }}</span>
          </div>
        </div>
        <img src="@/assets/icons/withdraw.svg" alt="Withdraw" class="withdraw-icon">
      </div>
    </div>

    <!-- Нижняя часть с ссылкой и кнопкой -->
    <div class="ref-footer">
      <div class="link-box" @click="copyLink">
        <div class="link-text">
          {{ inviteLinkDisplay }}
        </div>
        <img src="@/assets/icons/copy.svg" alt="Copy" class="copy-icon">
      </div>

      <button class="share-button" @click="shareLink">
        Share
      </button>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import lottie from 'lottie-web';
import api from '../api/client';
import { useAuthStore } from '../store/auth';
import { useAppStore } from '../store/app';
import { useNotificationStore } from '../store/notification';
import { connectWallet } from '../api/tonConnect';
import tonDogsLottie from '@/assets/icons/ton_dogs.json';
import starsDogsLottie from '@/assets/icons/stars_dogs.json';

export default {
  name: 'ReferralsView',
  setup() {
    const authStore = useAuthStore();
    const appStore = useAppStore();
    const lottieContainer = ref(null);
    let lottieInstance = null;
    const activeRefCurrency = ref('TON');
    const stats = ref({
      count: 0,
      total_ton: 0,
      total_stars: 0,
      locked_stars: 0,
      available_stars: 0,
      available_in_ton: 0,
      ref_percentage: 5,
      invite_link: ''
    });

    const inviteLinkDisplay = computed(() => {
      if (!stats.value.invite_link) return 't.me/bot_name/app?\nStartparam= refUUID';
      // Можно форматировать для отображения в две строки как на макете
      const url = stats.value.invite_link;
      if (url.includes('?')) {
        const [base, params] = url.split('?');
        return `${base}?\n${params}`;
      }
      return url;
    });

    const fetchStats = async () => {
      try {
        const response = await api.getReferralStats();
        // Благодаря перехватчику в api/client.js, response.data — это уже объект ReferralStats
        const data = response.data;
        
        // Используем процент из статистики, если он есть, иначе из общего конфига
        const refRate = data.ref_percentage || appStore.config.ref_percentage || 0.05;

        stats.value = {
          count: data.total_invited,
          total_ton: data.ton.total_earned,
          available_ton: data.ton.available_balance,
          total_stars: data.stars.total_earned,
          locked_stars: data.stars.locked_balance,
          available_stars: data.stars.available_balance,
          available_in_ton: data.stars.available_in_ton,
          ref_percentage: refRate * 100, // Конвертируем 0.05 в 5
          // Собираем ссылку (можно подтянуть юзернейм бота из настроек в будущем)
          invite_link: `https://t.me/stickerloot_bot/app?startapp=${data.referral_code}`
        };
      } catch (e) {
        console.error("Fetch referral stats failed", e);
      }
    };

    const toggleCurrency = () => {
      activeRefCurrency.value = activeRefCurrency.value === 'TON' ? 'STARS' : 'TON';
    };

    const handleWithdraw = async () => {
      const authStore = useAuthStore();
      const notificationStore = useNotificationStore();
      
      try {
        // Определяем сумму вывода: для TON — доступный баланс, для STARS — только доступная
        const amountToWithdraw = activeRefCurrency.value === 'TON' ? stats.value.available_ton : stats.value.available_stars;
        const minAmount = activeRefCurrency.value === 'TON' ? 0.1 : 10;
        
        if (!amountToWithdraw || parseFloat(amountToWithdraw) < minAmount) {
          notificationStore.error('Withdrawal error', `Minimum amount to withdraw is ${minAmount} ${activeRefCurrency.value}`);
          window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred('error');
          return;
        }

        // Отправляем запрос на бэкенд
        await api.withdrawReferrals({
          amount: parseFloat(amountToWithdraw),
          currency: activeRefCurrency.value
        });
        
        // Показываем уведомление и обновляем стату
        notificationStore.success('Success', `Withdrawal of ${amountToWithdraw} ${activeRefCurrency.value} initiated!`);
        window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred('success');
        fetchStats();
      } catch (e) {
        console.error("Withdrawal failed", e);
        
        const errorDetail = e.response?.data?.detail;
        if (errorDetail && errorDetail.includes("Wallet not connected")) {
          connectWallet();
        }
        // Убрали else if с notificationStore.error(), так как axios interceptor уже показал уведомление
        
        window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred('error');
      }
    };

    const updateLottie = (type) => {
      if (lottieInstance) {
        lottieInstance.destroy();
      }
      lottieInstance = lottie.loadAnimation({
        container: lottieContainer.value,
        renderer: 'svg',
        loop: true,
        autoplay: true,
        animationData: type === 'TON' ? tonDogsLottie : starsDogsLottie
      });
    };

    watch(activeRefCurrency, (newVal) => {
      updateLottie(newVal);
    });

    const copyLink = () => {
      if (stats.value.invite_link) {
        navigator.clipboard.writeText(stats.value.invite_link);
        // Можно добавить тост или HapticFeedback
        window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred('success');
      }
    };

    const shareLink = () => {
      const url = `https://t.me/share/url?url=${encodeURIComponent(stats.value.invite_link)}&text=${encodeURIComponent('Join me on Sticker Market!')}`;
      window.Telegram?.WebApp?.openTelegramLink(url);
    };

    onMounted(() => {
      fetchStats();
      updateLottie(activeRefCurrency.value);
    });

    onUnmounted(() => {
      if (lottieInstance) {
        lottieInstance.destroy();
      }
    });

    return {
      lottieContainer,
      activeRefCurrency,
      stats,
      inviteLinkDisplay,
      toggleCurrency,
      copyLink,
      shareLink,
      handleWithdraw
    };
  }
}
</script>

<style scoped>
.referrals-view {
  padding: 30px 0; /* Только вертикальный паддинг, блоки на всю ширину */
  display: flex;
  flex-direction: column;
  gap: 30px;
  min-height: calc(100vh - 100px);
  padding-bottom: 150px; /* Место для футера */
  position: relative;
}

.ref-promo-card {
  width: 100%;
  border-radius: 43px; /* Закругление 43 */
  background: var(--Test, linear-gradient(66.50deg, rgba(32, 30, 41, 1),rgba(40, 37, 59, 1)));
  padding: 25px 15px 15px 15px;
  display: flex;
  flex-direction: column;
  align-items: center;
  box-sizing: border-box;
  transition: background 0.3s ease;
}

.ref-promo-card.is-stars {
  background: var(--Test, linear-gradient(66.50deg, rgba(32, 30, 41, 1),rgba(40, 37, 59, 1)));
}

.ref-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 35px;
  align-self: center;
  padding: 0 20px;
}

.ref-header-icon {
  width: 17.2px;
  height: 17.2px;
  object-fit: contain;
  opacity: 0.5;
}

.ref-header-title {
  font-size: 19px;
  font-weight: 600;
  color: #FFFFFF;
}

.ref-promo-text {
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 30px;
}

.promo-line {
  font-size: 24px;
  font-weight: 600;
  color: #FFFFFF;
  line-height: 1.2;
}

.percent-pill {
  background: rgba(255, 255, 255, 0.1);
  padding: 4px 10px;
  border-radius: 1000px;
  font-size: 20px;
  vertical-align: middle;
}

.lottie-container {
  width: 158px;
  height: 158px;
  margin-bottom: 0px;
}

/* Слайдер валют */
.ref-currency-selector {
  align-self: flex-start;
  margin-bottom: 15px;
  cursor: pointer;
}

.ref-selector-bg {
  width: 80px;
  height: 32px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 1000px;
  position: relative;
  display: flex;
  align-items: center;
  padding: 2px;
  box-sizing: border-box;
}

.ref-selector-thumb {
  position: absolute;
  width: 38px;
  height: 28px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 1000px;
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 1;
}

.ref-selector-thumb.is-stars {
  transform: translateX(38px);
}

.ref-lang-option {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2;
  opacity: 0.5;
  transition: opacity 0.3s;
}

.ref-lang-option.active {
  opacity: 1;
}

.ref-curr-icon {
  width: 16px;
  height: 16px;
  object-fit: contain;
}

/* Статистика */
.stats-row {
  display: flex;
  gap: 12px;
  width: 100%;
  margin-bottom: 12px;
}

.stat-box {
  flex: 1;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 24px;
  padding: 15px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-value-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.stat-curr-icon {
  width: 16px;
  height: 16px;
  object-fit: contain;
}

.stat-number {
  font-size: 20px;
  font-weight: 600;
  color: #FFFFFF;
}

.stat-label {
  font-size: 17px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.5);
}

/* 21d locked row */
.locked-stars-row {
  width: 100%;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 20px;
  padding: 12px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-sizing: border-box;
  margin-bottom: 12px;
}

.locked-label {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.4);
  font-weight: 500;
}

.locked-right {
  display: flex;
  align-items: center;
  gap: 6px;
}

.locked-curr-icon {
  width: 16px;
  height: 16px;
}

.locked-number {
  font-size: 16px;
  font-weight: 600;
  color: #FFFFFF;
}

/* Блок вывода */
.withdraw-box {
  width: 100%;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 1000px;
  padding: 12px 25px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-sizing: border-box;
}

.withdraw-main {
  display: flex;
  align-items: center;
  gap: 12px;
}

.withdraw-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.withdraw-curr-icon {
  width: 16px;
  height: 16px;
}

.withdraw-number {
  font-size: 20px;
  font-weight: 600;
  color: #FFFFFF;
}

.ton-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 1000px;
  padding: 8px 12px;
}

.ton-pill-icon {
  width: 14px;
  height: 14px;
}

.ton-pill-text {
  font-size: 14px;
  font-weight: 600;
  color: #FFFFFF;
}

.withdraw-icon {
  width: 20px;
  height: 20px;
  opacity: 0.8;
}

/* Футер */
.ref-footer {
  position: fixed;
  bottom: 0;
  left: 0;
  width: 100%;
  padding: 0 20px 20px 20px;
  box-sizing: border-box;
  background: transparent;
  display: flex;
  flex-direction: column;
  gap: 16px;
  z-index: 100;
}

.link-box {
  width: 100%;
  background: #232323;
  border-radius: 30px; /* Закругление 30 */
  padding: 16px 20px; /* Немного уменьшен вертикальный паддинг */
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-sizing: border-box;
  cursor: pointer;
  transition: transform 0.1s ease; /* Добавляем транзишн для анимации */
  gap: 12px;
  overflow: hidden;
}

.link-box:active {
  transform: scale(0.96); /* Эффект проседания вниз (вдавливания) */
}

.link-text {
  font-size: 16px; /* Уменьшен размер шрифта, чтобы влезала ссылка */
  font-weight: 500;
  color: #FFFFFF;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.3;
  flex: 1;
  min-width: 0;
}

.copy-icon {
  flex-shrink: 0;
  width: 24.64px;
  height: 27.37px;
  object-fit: contain;
}

.share-button {
  width: 100%;
  background: #FFFFFF;
  color: #000000;
  border: none;
  border-radius: 1000px;
  padding: 21px;
  font-size: 19px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.1s ease;
}

.share-button:active {
  transform: scale(0.98);
}
</style>
