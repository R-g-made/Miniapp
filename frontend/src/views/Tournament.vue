<template>
  <div class="tournament-view">
    <div class="header-card">
      <h1 class="title">Volume Tournament</h1>
      <p class="subtitle">Open pack more and climb to the top<br>with this leaderboard</p>
      
      <div class="timer-container">
        <div v-if="isActive && timeLeft" class="timer-pills">
          <div class="timer-pill">{{ timeLeft.days }}D</div>
          <span class="colon">:</span>
          <div class="timer-pill">{{ timeLeft.hours }}H</div>
          <span class="colon">:</span>
          <div class="timer-pill">{{ timeLeft.minutes }}m</div>
        </div>
        <div v-else class="timer-finished">
          Finished
        </div>
      </div>

      <div class="lottie-container" ref="lottieContainer"></div>

      <div class="how-it-works">
        <div class="how-it-works-header" @click="toggleHowItWorks">
          <span>How it work?</span>
          <svg :class="{ 'rotated': isHowItWorksOpen }" width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M6 9L12 15L18 9" stroke="#8E8E93" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <div class="content-wrapper" :class="{ 'is-open': isHowItWorksOpen }">
          <div class="how-it-works-content">
            Open pack more and climb to the top with this leaderboard
          </div>
        </div>
      </div>
    </div>

    <div class="leaderboard-card">
      <div class="leaderboard-item user-item">
        <div class="item-left">
          <div class="avatar-wrapper">
            <img v-if="userAvatar" :src="userAvatar" class="avatar" />
            <div v-else class="avatar-placeholder">{{ userInitials }}</div>
          </div>
          <div class="user-info">
            <span class="username">You</span>
            <span class="divider">|</span>
            <span class="rank">№{{ currentUserPlace }}</span>
          </div>
        </div>
        <div class="item-right">
          <div class="volume-block">
            <img src="@/assets/icons/ton.svg" class="currency-icon" />
            <span class="volume">{{ currentUserVolume }}</span>
          </div>
        </div>
      </div>

      <div class="leaderboard-list">
        <div v-for="user in leaderboard" :key="user.user_id" class="leaderboard-item">
          <div class="item-left">
            <div class="avatar-wrapper">
              <img v-if="user.avatar_url" :src="user.avatar_url" class="avatar" />
              <div v-else class="avatar-placeholder">{{ getInitials(user.username) }}</div>
            </div>
            <div class="user-info">
              <span class="rank-list">№{{ user.place }}</span>
              <span class="divider">|</span>
              <span class="username">{{ user.username || 'Anonymous' }}</span>
            </div>
          </div>
          <div class="item-right">
            <div class="volume-block">
              <img src="@/assets/icons/ton.svg" class="currency-icon" />
              <span class="volume">{{ user.volume }}</span>
            </div>
            <img v-if="user.prize_picture_url" :src="user.prize_picture_url" class="prize-icon" />
            <div v-else-if="user.ton_reward" class="ton-reward-pill">
              <img src="@/assets/icons/ton.svg" class="currency-icon" />
              <span class="ton-reward-text">{{ user.ton_reward }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useAuthStore } from '../store/auth';
import apiClient from '../api/client';
import lottie from 'lottie-web';

export default {
  name: 'Tournament',
  setup() {
    const authStore = useAuthStore();
    const lottieContainer = ref(null);
    let animationInstance = null;

    const isActive = ref(false);
    const endTimeStr = ref(null);
    const currentUserPlace = ref('50+');
    const currentUserVolume = ref(0);
    const leaderboard = ref([]);
    const isHowItWorksOpen = ref(false);
    const timeLeft = ref(null);
    let timerInterval = null;

    const userAvatar = computed(() => authStore.user?.photo_url);
    const userInitials = computed(() => {
      const name = authStore.user?.first_name || 'U';
      return name.charAt(0).toUpperCase();
    });

    const getInitials = (name) => {
      if (!name) return 'A';
      return name.charAt(0).toUpperCase();
    };

    const toggleHowItWorks = () => {
      isHowItWorksOpen.value = !isHowItWorksOpen.value;
    };

    const calculateTimeLeft = () => {
      if (!endTimeStr.value) {
        timeLeft.value = null;
        return;
      }

      // Формат "DD.MM.YYYY HH:mm:ss" предполагается по беку
      // Нужно парсить корректно
      const parts = endTimeStr.value.split(' ');
      if (parts.length !== 2) return;
      const dateParts = parts[0].split('.');
      const timeParts = parts[1].split(':');
      if (dateParts.length !== 3 || timeParts.length !== 3) return;

      const endDate = new Date(Date.UTC(
        parseInt(dateParts[2]),
        parseInt(dateParts[1]) - 1,
        parseInt(dateParts[0]),
        parseInt(timeParts[0]),
        parseInt(timeParts[1]),
        parseInt(timeParts[2])
      ));

      const now = new Date();
      const diff = endDate.getTime() - now.getTime();

      if (diff <= 0) {
        timeLeft.value = null;
        isActive.value = false;
        if (timerInterval) clearInterval(timerInterval);
        return;
      }

      const days = Math.floor(diff / (1000 * 60 * 60 * 24));
      const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

      timeLeft.value = { days, hours, minutes };
    };

    const fetchData = async () => {
      try {
        const res = await apiClient.getLeaderboard();
        const data = res.data;
        isActive.value = data.is_active;
        endTimeStr.value = data.end_time;
        currentUserPlace.value = data.current_user_place;
        currentUserVolume.value = data.current_user_volume;
        leaderboard.value = data.leaderboard;

        calculateTimeLeft();
        if (isActive.value && endTimeStr.value) {
          timerInterval = setInterval(calculateTimeLeft, 60000); // Обновляем каждую секунду для мгновенной реакции
        }
      } catch (e) {
        console.error('Failed to fetch leaderboard:', e);
      }
    };

    onMounted(async () => {
      await fetchData();
      
      import('../assets/icons/tournament.json').then((animationData) => {
        if (lottieContainer.value) {
          animationInstance = lottie.loadAnimation({
            container: lottieContainer.value,
            renderer: 'svg',
            loop: true,
            autoplay: true,
            animationData: animationData.default
          });
        }
      });
    });

    onUnmounted(() => {
      if (timerInterval) clearInterval(timerInterval);
      if (animationInstance) animationInstance.destroy();
    });

    return {
      lottieContainer,
      isActive,
      timeLeft,
      isHowItWorksOpen,
      toggleHowItWorks,
      userAvatar,
      userInitials,
      currentUserPlace,
      currentUserVolume,
      leaderboard,
      getInitials
    };
  }
}
</script>

<style scoped>
.tournament-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-bottom: 20px;
}

.header-card {
  background: linear-gradient(126.87deg, rgba(67, 76, 199, 0.1) 14.318%, rgba(220, 136, 213, 0.1) 85.682%);
  border-radius: 39px;
  padding: 24px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.title {
  font-size: 22px;
  font-weight: 600;
  color: #fff;
  margin: 0 0 8px 0;
}

.subtitle {
  font-size: 17px;
  color: #8E8E93;
  margin: 0 0 24px 0;
  line-height: 1.4;
}

.timer-container {
  margin-bottom: 24px;
}

.timer-pills {
  display: flex;
  align-items: center;
  gap: 8px;
}

.timer-pill {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 19px;
  padding: 8px 16px;
  color: #fff;
  font-size: 14px;
  font-weight: 500;
}

.colon {
  color: #8E8E93;
  font-weight: 500;
}

.timer-finished {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 100px;
  padding: 8px 24px;
  color: #fff;
  font-size: 14px;
  font-weight: 500;
}

.lottie-container {
  width: 143px;
  height: 143px;
  margin-bottom: 24px;
}

.how-it-works {
  width: 100%;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 30px;
  overflow: hidden;
}

.how-it-works-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  height: 58px;
  color: #fff;
  font-size: 17px;
  font-weight: 500;
  cursor: pointer;
}

.how-it-works-header svg {
  transition: transform 0.3s ease;
}

.rotated {
  transform: rotate(-180deg);
}

.content-wrapper {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 0.3s ease;
}

.content-wrapper.is-open {
  grid-template-rows: 1fr;
}

.how-it-works-content {
  overflow: hidden;
  padding: 0 20px;
  color: #8E8E93;
  font-size: 16px;
  line-height: 1.4;
  text-align: left;
}

.content-wrapper.is-open .how-it-works-content {
  padding-bottom: 20px;
}

.leaderboard-card {
  background: #1c1c1e;
  border-radius: 31px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.leaderboard-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
}

.user-item {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 1000px;
  height: 58px;
  box-sizing: border-box;
  padding: 0 16px;
  margin-bottom: 8px;
}

.item-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.avatar-wrapper {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  overflow: hidden;
  flex-shrink: 0;
  background: #2c2c2e;
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-placeholder {
  color: #fff;
  font-size: 16px;
  font-weight: 600;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.username {
  color: #fff;
  font-size: 17px;
  font-weight: 500;
}

.divider {
  color: #3A3A3C;
  font-size: 17px;
}

.rank, .rank-list {
  color: #8E8E93;
  font-size: 17px;
}

.item-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.volume-block {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 1000px;
  padding: 6px 12px;
}

.currency-icon {
  width: 16px;
  height: 16px;
}

.volume {
  color: #fff;
  font-size: 14px;
  font-weight: 600;
}

.prize-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
}

.ton-reward-pill {
  display: flex;
  align-items: center;
  gap: 4px;
  background: #15242C;
  border-radius: 1000px;
  padding: 6px 10px;
}

.ton-reward-text {
  color: #39A5ED;
  font-size: 14px;
  font-weight: 600;
}
</style>
