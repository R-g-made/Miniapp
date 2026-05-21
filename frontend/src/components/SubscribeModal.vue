<template>
  <div class="subscribe-modal-root">
    <Transition name="overlay-fade">
      <div v-if="isOpen" class="modal-overlay" @click="closeModal"></div>
    </Transition>

    <Transition name="modal-slide">
      <div v-if="isOpen" class="modal-wrapper" @click="closeModal">
        <div class="subscribe-modal" @click.stop>
          <div class="modal-content">
            <div class="lottie-wrapper" ref="lottieContainer"></div>
            
            <h2 class="modal-title">
              Subscribe to our <span class="highlight">Channel</span>
            </h2>
            
            <p class="modal-subtitle">
              To avoid missing the latest news<br>and giveaways
            </p>
            
            <button class="subscribe-btn" @click="handleSubscribe">
              <span>Subscribe</span>
              <img src="@/assets/icons/telegram.svg" alt="Telegram" class="tg-icon">
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted, nextTick } from 'vue';
import { useAppStore } from '../store/app';
import { storeToRefs } from 'pinia';
import lottie from 'lottie-web';
import subscribePromoLottie from '@/assets/icons/Subscribe_promo.json';

export default {
  name: 'SubscribeModal',
  setup() {
    const appStore = useAppStore();
    const isOpen = computed(() => appStore.isSubscribeModalOpen);
    const lottieContainer = ref(null);
    let lottieInstance = null;

    const closeModal = () => {
      appStore.setSubscribeModalOpen(false);
      // Запоминаем, что пользователь уже видел модалку в этой сессии
      sessionStorage.setItem('subscribeModalShown', 'true');
    };

    const handleSubscribe = () => {
      if (window.Telegram?.WebApp?.openTelegramLink) {
        window.Telegram.WebApp.openTelegramLink('https://t.me/stickerloots');
      } else {
        window.open('https://t.me/stickerloots', '_blank');
      }
      closeModal();
    };

    const initLottie = async () => {
      if (!lottieContainer.value || lottieInstance) return;
      
      lottieInstance = lottie.loadAnimation({
        container: lottieContainer.value,
        renderer: 'svg',
        loop: true,
        autoplay: true,
        animationData: subscribePromoLottie
      });
    };

    watch(isOpen, async (newVal) => {
      if (newVal) {
        await nextTick();
        initLottie();
      } else if (lottieInstance) {
        lottieInstance.destroy();
        lottieInstance = null;
      }
    });

    onMounted(() => {
      // Проверяем, показывали ли мы уже модалку в этой сессии
      const hasBeenShown = sessionStorage.getItem('subscribeModalShown');
      
      if (!hasBeenShown) {
        // Небольшая задержка перед показом, чтобы приложение успело загрузиться
        setTimeout(() => {
          appStore.setSubscribeModalOpen(true);
        }, 1500);
      }
    });

    return {
      isOpen,
      closeModal,
      handleSubscribe,
      lottieContainer
    };
  }
}
</script>

<style scoped>
.subscribe-modal-root {
  position: relative;
  z-index: 100;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(8px);
}

.modal-wrapper {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  pointer-events: none;
}

.subscribe-modal {
  pointer-events: auto;
  width: calc(100% - 40px);
  max-width: 500px;
  margin-bottom: calc(20px + env(keyboard-inset-height, 0px));
  background: #171717;
  border-radius: 48px;
  padding: 40px 20px 30px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  transition: margin-bottom 0.3s ease-out;
  will-change: transform;
}

.modal-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.lottie-wrapper {
  width: 200px;
  height: 200px;
  margin-bottom: 24px;
}

.modal-title {
  font-size: 24px;
  font-weight: 700;
  color: #FFFFFF;
  margin: 0 0 12px 0;
  line-height: 1.2;
}

.highlight {
  background: linear-gradient(270.00deg, rgba(104, 144, 246, 1) 0%, rgba(255, 255, 255, 1) 50%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  color: transparent;
}

.modal-subtitle {
  font-size: 15px;
  font-weight: 400;
  color: rgba(255, 255, 255, 0.5);
  margin: 0 0 32px 0;
  line-height: 1.4;
}

.subscribe-btn {
  width: 100%;
  height: 60px;
  background: #FFFFFF;
  border-radius: 1000px;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 17px;
  font-weight: 600;
  color: #000000;
  cursor: pointer;
  transition: opacity 0.2s;
}

.subscribe-btn:active {
  opacity: 0.8;
}

.tg-icon {
  width: 20px;
  height: 20px;
}

/* Transitions */
.overlay-fade-enter-active,
.overlay-fade-leave-active {
  transition: opacity 0.3s ease;
}
.overlay-fade-enter-from,
.overlay-fade-leave-to {
  opacity: 0;
}

.modal-slide-enter-active,
.modal-slide-leave-active {
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.modal-slide-enter-from {
  transform: translateY(100%);
}
.modal-slide-leave-to {
  transform: translateY(100%);
}
</style>