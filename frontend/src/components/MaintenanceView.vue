<template>
  <div class="maintenance-screen">
    <div class="maintenance-content">
      <div class="maintenance-lottie" ref="lottieContainer"></div>
      <h2 class="maintenance-title">Project is updating</h2>
      <p class="maintenance-text">Will be available shortly</p>
    </div>
    
    <div class="maintenance-footer">
      <button class="reload-btn" @click="reloadApp">Reload</button>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue';
import lottie from 'lottie-web';
import { useAuthStore } from '../store/auth';
import { useAppStore } from '../store/app';

export default {
  name: 'MaintenanceView',
  setup() {
    const lottieContainer = ref(null);
    const authStore = useAuthStore();
    const appStore = useAppStore();
    let anim = null;

    onMounted(async () => {
      try {
        // Убедись, что регистр имени файла совпадает с тем, что в папке!
        const animationData = await import('@/assets/icons/Dogs_update.json');
        if (lottieContainer.value) {
          anim = lottie.loadAnimation({
            container: lottieContainer.value,
            renderer: 'svg',
            loop: true,
            autoplay: true,
            animationData: animationData.default || animationData
          });
        }
      } catch (error) {
        console.error("Failed to load Lottie animation", error);
      }
    });

    onUnmounted(() => {
      if (anim) anim.destroy();
    });

    const reloadApp = async () => {
      const tg = window.Telegram?.WebApp;
      if (tg && tg.HapticFeedback) {
        tg.HapticFeedback.impactOccurred('light');
      }
      
      authStore.isLoading = true;
      const success = await authStore.initialize();
      
      // Если получилось авторизоваться (например, мы отключили UNAVAILABLE_MODE)
      if (success) {
        appStore.setMaintenance(false);
      }
    };

    return { lottieContainer, reloadApp };
  }
}
</script>

<style scoped>
.maintenance-screen {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: #171717;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  box-sizing: border-box;
}

.maintenance-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
}

.maintenance-lottie {
  width: 150px;
  height: 150px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.maintenance-title {
  color: #FFFFFF;
  font-size: 20px;
  font-weight: 500;
  margin: 0;
  text-align: center;
}

.maintenance-text {
  color: rgba(255, 255, 255, 0.5);
  font-size: 16px;
  font-weight: 500;
  margin: 0;
  text-align: center;
}

.maintenance-footer {
  /* Отступ снизу такой же, как у навбара */
  padding: 0 20px calc(35px + env(safe-area-inset-bottom, 0px)) 20px;
  width: 100%;
  box-sizing: border-box;
}

.reload-btn {
  width: 100%;
  height: 52px;
  background-color: #FFFFFF;
  color: #000000;
  border: none;
  border-radius: 1000px;
  font-size: 17px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.1s;
}

.reload-btn:active {
  transform: scale(0.95);
}
</style>