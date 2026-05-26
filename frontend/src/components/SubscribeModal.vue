<template>
  <div class="subscribe-modal-root">
    <!-- Затемнение фона -->
    <Transition name="overlay-fade">
      <div v-if="isOpen" class="modal-overlay" @click="closeModal"></div>
    </Transition>

    <!-- Сама модалка -->
    <Transition name="modal-slide">
      <div v-if="isOpen" class="modal-wrapper" @click="closeModal">
        <div 
          class="subscribe-modal" 
          @click.stop 
          @touchstart="handleTouchStart"
          @touchmove="handleTouchMove"
          @touchend="handleTouchEnd"
          :style="modalStyle"
        >
          
          <div class="modal-drag-handle"></div>

          <div class="lottie-container" ref="lottieContainer"></div>

          <h2 class="modal-title">
            Subscribe to our <span class="gradient-text">Channel</span>
          </h2>
          
          <p class="modal-subtitle">
            To avoid missing the latest news and giveaways
          </p>

          <button class="subscribe-btn" @click="handleSubscribe">
            <span>Subscribe</span>
            <img src="@/assets/icons/telegram.svg" alt="Telegram" class="tg-icon">
          </button>

        </div>
      </div>
    </Transition>
  </div>
</template>

<script>
import { ref, onMounted, watch, onUnmounted, computed } from 'vue';
import lottie from 'lottie-web';
import subscribeLottie from '@/assets/icons/Subscribe_promo.json';

export default {
  name: 'SubscribeModal',
  setup() {
    const isOpen = ref(false);
    const lottieContainer = ref(null);
    let lottieInstance = null;

    // Свайп вниз
    const touchStartY = ref(0);
    const touchCurrentY = ref(0);
    const translateY = ref(0);
    const isDragging = ref(false);

    const handleTouchStart = (e) => {
      touchStartY.value = e.touches[0].clientY;
      touchCurrentY.value = e.touches[0].clientY;
      isDragging.value = true;
    };

    const handleTouchMove = (e) => {
      if (!isDragging.value) return;
      touchCurrentY.value = e.touches[0].clientY;
      const diff = touchCurrentY.value - touchStartY.value;
      if (diff > 0) {
        translateY.value = diff;
      }
    };

    const handleTouchEnd = () => {
      isDragging.value = false;
      if (translateY.value > 100) {
        closeModal();
      }
      translateY.value = 0;
    };

    const modalStyle = computed(() => {
      if (translateY.value === 0 && !isDragging.value) return {};
      return {
        transform: `translateY(${translateY.value}px)`,
        transition: isDragging.value ? 'none' : 'transform 0.3s ease'
      };
    });

    onMounted(() => {
      // Проверяем время последнего показа
      const lastSeenTime = localStorage.getItem('lastSeenSubscribePromo');
      const currentTime = new Date().getTime();
      const twelveHoursInMs = 12 * 60 * 60 * 1000; // 12 часов в миллисекундах

      if (!lastSeenTime || (currentTime - parseInt(lastSeenTime)) > twelveHoursInMs) {
        // Показываем с небольшой задержкой для плавности
        setTimeout(() => {
          isOpen.value = true;
          localStorage.setItem('lastSeenSubscribePromo', currentTime.toString());
        }, 1000);
      }
    });

    watch(isOpen, (newVal) => {
      if (newVal) {
        setTimeout(() => {
          if (lottieContainer.value && !lottieInstance) {
            lottieInstance = lottie.loadAnimation({
              container: lottieContainer.value,
              renderer: 'svg',
              loop: true,
              autoplay: true,
              animationData: subscribeLottie
            });
          }
        }, 50); // Ждем рендера DOM
      } else {
        if (lottieInstance) {
          lottieInstance.destroy();
          lottieInstance = null;
        }
      }
    });

    onUnmounted(() => {
      if (lottieInstance) {
        lottieInstance.destroy();
      }
    });

    const closeModal = () => {
      isOpen.value = false;
    };

    const handleSubscribe = () => {
      // Если пользователь нажал подписаться, не показываем модалку 1 неделю
      const oneWeekInMs = new Date().getTime() + (7 * 24 * 60 * 60 * 1000); // +1 неделя
      localStorage.setItem('lastSeenSubscribePromo', oneWeekInMs.toString());

      const tg = window.Telegram?.WebApp;
      if (tg && tg.openTelegramLink) {
        // Открытие ссылки внутри Telegram
        tg.openTelegramLink('https://t.me/stickerloots');
      } else {
        // Фолбэк для браузера
        window.open('https://t.me/stickerloots', '_blank');
      }
      closeModal();
    };

    return {
      isOpen,
      closeModal,
      handleSubscribe,
      lottieContainer,
      handleTouchStart,
      handleTouchMove,
      handleTouchEnd,
      modalStyle
    };
  }
}
</script>

<style scoped>
.subscribe-modal-root {
  position: relative;
  z-index: 2000; /* Выше NavBar (у которого 1000) */
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
  background: #202020;
  border-radius: 48px;
  padding: 16px 20px 20px 20px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  align-items: center;
  transition: transform 0.3s ease;
}

.modal-drag-handle {
  width: 60px;
  height: 4px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 100px;
  margin-bottom: 20px;
}

.lottie-container {
  width: 160px;
  height: 160px;
  margin-bottom: 15px;
}

.modal-title {
  font-size: 21px;
  font-weight: 700;
  color: #FFFFFF;
  margin: 0 0 12px 0;
  text-align: center;
}

.gradient-text {
  background: linear-gradient(270deg, #5A98F2, #ffffffff); /* Перевернутый синий градиент */
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.modal-subtitle {
  font-size: 15px;
  font-weight: 400;
  color: rgba(255, 255, 255, 0.5);
  text-align: center;
  margin: 0 0 30px 0;
  line-height: 1.4;
  padding: 0 10px;
}

.subscribe-btn {
  width: 100%;
  background: #FFFFFF;
  border: none;
  border-radius: 1000px;
  padding: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  cursor: pointer;
  transition: transform 0.15s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.subscribe-btn:active {
  transform: scale(0.96);
}

.subscribe-btn span {
  font-size: 18px;
  font-weight: 600;
  color: #000000;
}

.tg-icon {
  width: 20px;
  height: 20px;
  object-fit: contain;
}

/* Анимации появления */
.overlay-fade-enter-active,
.overlay-fade-leave-active {
  transition: opacity 0.4s ease;
}
.overlay-fade-enter-from,
.overlay-fade-leave-to {
  opacity: 0;
}

.modal-slide-enter-active,
.modal-slide-leave-active {
  transition: opacity 0.4s cubic-bezier(0.4, 0, 0.2, 1), transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}
.modal-slide-enter-from,
.modal-slide-leave-to {
  opacity: 0;
  transform: translateY(100%);
}
</style>