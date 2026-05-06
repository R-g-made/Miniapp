<template>
  <div class="case-view">
    <div class="live-drop-wrapper">
      <LiveDrop />
    </div>

    <div v-if="loading" class="loading-container">
      <div class="loader"></div>
    </div>

    <div v-else-if="currentCase" class="case-content">
      <div class="case-header">
        <div class="case-title-row">
          <img src="@/assets/icons/box.svg" alt="Case" class="case-icon">
          <h2 class="case-title">{{ currentCase.name }}</h2>
        </div>
      </div>

      <!-- Спиннер -->
      <div class="spinner-section">
        <!-- Указатель (SVG курсор) -->
        <img src="@/assets/icons/cursor.svg" alt="Pointer" class="spinner-pointer">
        
        <div class="spinner-container">
          <!-- Обертка для карточек -->
          <div class="spinner-track-wrapper">
            <div class="spinner-track" :style="trackStyle">
              <div 
                v-for="(item, index) in displayItems" 
                :key="index" 
                class="spinner-card"
                :class="{ 'main-card': index === centeredIndex }"
                :style="getCardStyle(index)"
              >
                <img :src="item.image_url" :alt="item.name" class="sticker-img" :style="getStickerStyle(index)">
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Кнопки управления (теперь выше содержимого) -->
      <div class="case-actions">
        <!-- Основная белая кнопка (всегда на месте, меняется только контент) -->
        <button 
          :class="['btn-open-main', { 'btn-sell': isResultMode }]" 
          :disabled="isSpinning || isAwaitingResult || (!isResultMode && currentCase.is_active === false)" 
          @click="isResultMode ? sellWinningSticker() : startRealSpin()"
        >
          <template v-if="isSpinning || isAwaitingResult">
            <span class="btn-text">{{ isAwaitingResult ? 'Opening...' : 'Spinning' }}</span>
          </template>
          <template v-else-if="isResultMode">
            <span class="btn-text">Sell for {{ formatPrice(winningItem) }}</span>
            <img 
              v-if="activeCurrency === 'TON'"
              src="@/assets/icons/ton.svg" 
              alt="TON" 
              class="btn-ton-icon"
            >
            <img 
              v-else
              src="@/assets/icons/star.svg" 
              alt="STARS" 
              class="btn-ton-icon stars"
            >
          </template>
          <template v-else>
            <span class="btn-text">Open for {{ formatPrice(currentCase) }}</span>
            <img 
              v-if="activeCurrency === 'TON'"
              src="@/assets/icons/ton.svg" 
              alt="TON" 
              class="btn-ton-icon"
            >
            <img 
              v-else
              src="@/assets/icons/star.svg" 
              alt="STARS" 
              class="btn-ton-icon stars"
            >
          </template>
        </button>

        <!-- Кнопка Demo/Keep (исчезает и появляется с анимацией) -->
        <Transition name="button-pop">
          <button 
            v-if="!isSpinning && !isAwaitingResult" 
            class="btn-open-demo" 
            @click="isResultMode ? resetCase() : startDemoSpin()"
          >
            {{ isResultMode ? 'Keep' : 'Demo' }}
          </button>
        </Transition>
      </div>

      <!-- Содержимое кейса (теперь ниже кнопок) -->
      <div 
        class="case-contain-section"
        :style="containerBgStyle"
      >
        <div class="contain-header">
          <img src="@/assets/icons/box.svg" alt="Box" class="contain-icon">
          <h3 class="contain-title">Pack contain</h3>
        </div>

        <div class="catalog-scroll-wrapper">
          <div class="catalog-grid">
            <div 
              v-for="item in catalogItems" 
              :key="item.id" 
              class="catalog-item"
              @click="playCatalogLottie(item)"
            >
              <!-- Шанс (пилюля в верхнем правом углу) -->
              <div class="chance-badge">
                {{ formatChance(item.chance) }}%
              </div>
              
              <!-- Стиккер -->
              <div class="sticker-container">
                <div 
                  v-if="playingLottieId === item.id" 
                  class="catalog-animation-container"
                  :ref="el => { if (el) lottieContainers[item.id] = el }"
                >
                  <video 
                    v-if="getAnimationType(item) === 'webm'" 
                    :src="item.lottie_url" 
                    autoplay 
                    muted 
                    playsinline 
                    @ended="stopAnimation(item.id)"
                    class="catalog-video"
                  ></video>
                </div>
                <img v-else :src="item.image_url" :alt="item.name" class="catalog-sticker-img">
              </div>

              <!-- Цена (пилюля снизу) -->
              <div class="price-badge">
                <img 
                  v-if="activeCurrency === 'TON'"
                  src="@/assets/icons/ton.svg" 
                  alt="TON" 
                  class="price-icon"
                >
                <img 
                  v-else
                  src="@/assets/icons/star.svg" 
                  alt="STARS" 
                  class="price-icon"
                >
                <span class="price-text">{{ formatPrice(item) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <div v-else class="error-container">
      <p>Case not found</p>
      <router-link to="/" class="btn-open-demo">Back to Home</router-link>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import api from '../api/client';
import { useAuthStore } from '../store/auth';
import { useAppStore } from '../store/app';
import { useNotificationStore } from '../store/notification';
import { storeToRefs } from 'pinia';
import LiveDrop from '../components/LiveDrop.vue';

export default {
  name: 'CaseView',
  components: {
    LiveDrop
  },
  setup() {
    const route = useRoute();
    const router = useRouter();
    const appStore = useAppStore();
    const authStore = useAuthStore();
    const notificationStore = useNotificationStore();
    const { activeCurrency } = storeToRefs(appStore);
    
    const currentCase = ref(null);
    const loading = ref(true);
    const catalogItems = ref([]);

    // Состояния спина
    const isSpinning = ref(false);
    const isResultMode = ref(false);
    const winningItem = ref(null);
    const transitionTime = ref(0);
    const displayItems = ref([]);
    const isDemoSpinMode = ref(false);
    
    const step = 190; 
    const initialOffset = -95;
    const offset = ref(initialOffset);

    // Вспомогательные функции
    const formatPrice = (item) => {
      if (!item) return '0';
      if (activeCurrency.value === 'TON') {
        const val = item.price_ton || item.floor_price_ton || '0';
        return parseFloat(val).toFixed(2);
      }
      const val = item.price_stars || item.floor_price_stars || '0';
      return Math.round(parseFloat(val)).toString();
    };

    const formatChance = (chance) => {
      if (chance === undefined || chance === null) return '0';
      // Если шанс > 1, значит он уже в процентах (старые данные)
      // Если < 1, переводим в проценты
      const val = chance <= 1 ? (chance * 100) : chance;
      return parseFloat(val).toFixed(2).replace(/\.?0+$/, '');
    };

    const buildGradient = (styles, key) => {
      if (!styles) return null;
      
      const colors = styles[key] || styles[`${key}_gradient`];
      if (!colors) return null;
      
      if (!Array.isArray(colors)) {
        return `linear-gradient(0deg, ${colors}, ${colors})`;
      }
      
      const rotate = styles[`${key}_rotate`] || 
                    styles[`${key}_gradient_rotate`] || 
                    styles.rotate || 
                    "180deg";
      
      return `linear-gradient(${rotate}, ${colors.join(', ')})`;
    };

    const containerBgStyle = computed(() => {
      if (!currentCase.value) return {};
      const gradient = buildGradient(currentCase.value.styles, "container_bg") || 
                      buildGradient(currentCase.value.styles, "case_container");
      return gradient ? { background: gradient } : {};
    });

    const fetchCaseData = async () => {
      loading.value = true;
      try {
        const slug = route.params.slug;
        const response = await api.getCase(slug);
        const caseData = response.data;
        currentCase.value = caseData;
        
        // Мапим айтемы каталога
        catalogItems.value = caseData.items.map(item => ({
          id: item.id,
          sticker_id: item.sticker_id,
          name: item.name,
          image_url: item.image_url,
          lottie_url: item.lottie_url,
          chance: item.chance,
          price_ton: item.price_ton,
          price_stars: item.price_stars
        }));

        // Инициализируем displayItems для idle-анимации
        displayItems.value = [...catalogItems.value, ...catalogItems.value, ...catalogItems.value, ...catalogItems.value, ...catalogItems.value, ...catalogItems.value];
        
        // Рандомный начальный оффсет
        offset.value = initialOffset - (Math.floor(Math.random() * catalogItems.value.length) * step);
        
        startIdleAnimation();
      } catch (e) {
        console.error("Failed to fetch case:", e);
      } finally {
        loading.value = false;
      }
    };

    const isAwaitingResult = ref(false);
    const pendingInactivityRedirect = ref(false);

    const startRealSpin = async () => {
      if (isSpinning.value || isAwaitingResult.value) return;
      
      isDemoSpinMode.value = false;
      isAwaitingResult.value = true;
      try {
        // 1. Сначала запрос на бэк
        const response = await api.openCase(currentCase.value.slug, activeCurrency.value.toLowerCase());
        const wonSticker = response.data.drop;
        const newBalance = response.data.new_balance;
        
        // 2. Только после получения ответа готовим анимацию
        authStore.updateBalance(newBalance, activeCurrency.value);
        
        cancelAnimationFrame(idleAnimationFrame);
        isSpinning.value = true;
        isAwaitingResult.value = false;
        isResultMode.value = false;
        
        // 3. Подготовка ТОЧНОЙ дорожки (победитель на 50-й позиции)
        const trackItems = [];
        for (let i = 0; i < 60; i++) {
          const randomItem = catalogItems.value[Math.floor(Math.random() * catalogItems.value.length)];
          trackItems.push({ ...randomItem });
        }
        
        const winner = {
          id: wonSticker.id, // Поменял uuid на id
          sticker_id: wonSticker.id,
          name: wonSticker.name,
          image_url: wonSticker.image_url,
          lottie_url: wonSticker.lottie_url,
          price_ton: wonSticker.floor_price_ton,
          price_stars: wonSticker.floor_price_stars
        };
        
        trackItems[50] = winner;
        winningItem.value = winner;
        displayItems.value = trackItems;

        // 4. Запуск анимации спина (5 секунд)
        performSpinAnimation(50);
        
      } catch (e) {
        isAwaitingResult.value = false;
        // Если стикеров нет или кейс неактивен — сразу на главную
        const errorDetail = e.response?.data?.detail || "";
        if (errorDetail.includes("unavailable") || errorDetail.includes("stock") || errorDetail.includes("active")) {
          router.push('/');
        } else {
          notificationStore.addNotification(errorDetail || "Ошибка открытия кейса", 'error');
        }
      }
    };

    const performSpinAnimation = (targetIndex) => {
      const startTime = performance.now();
      const duration = 5000; 
      const currentOffset = offset.value;
      const randomShift = (Math.random() - 0.5) * 140;
      const targetOffset = -(targetIndex * step + 95 + randomShift);

      const easeOutQuint = (t) => 1 - Math.pow(1 - t, 5);

      const animateSpin = (currentTime) => {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easedProgress = easeOutQuint(progress);
        
        offset.value = currentOffset + (targetOffset - currentOffset) * easedProgress;

        if (progress < 1) {
          requestAnimationFrame(animateSpin);
        } else {
          setTimeout(() => {
            const finalStartTime = performance.now();
            const finalDuration = 400;
            const stopOffset = offset.value;
            const finalTargetOffset = -(targetIndex * step + 95);

            const animateFinal = (finalTime) => {
              const finalElapsed = finalTime - finalStartTime;
              const finalProgress = Math.min(finalElapsed / finalDuration, 1);
              const finalEased = 1 - Math.pow(1 - finalProgress, 3);

              offset.value = stopOffset + (finalTargetOffset - stopOffset) * finalEased;

              if (finalProgress < 1) {
                requestAnimationFrame(animateFinal);
              } else {
                isSpinning.value = false;
                isResultMode.value = true;
              }
            };
            requestAnimationFrame(animateFinal);
          }, 300);
        }
      };

      transitionTime.value = 0; 
      requestAnimationFrame(animateSpin);
    };

    const sellWinningSticker = async () => {
      if (!winningItem.value) return;
      
      if (isDemoSpinMode.value) {
        resetCase();
        return;
      }
      
      try {
        const response = await api.sellSticker(winningItem.value.id, activeCurrency.value.toLowerCase());
        const newBalance = response.data.new_balance;
        
        // Обновляем баланс в сторе
        authStore.updateBalance(newBalance, activeCurrency.value);

        resetCase();
        
        // Если за это время пришел сигнал о неактивности кейса — уходим на главную
        if (pendingInactivityRedirect.value) {
          router.push('/');
        }
      } catch (e) {
        notificationStore.addNotification(e.response?.data?.detail || "Ошибка продажи", 'error');
      }
    };

    const startDemoSpin = () => {
      if (isSpinning.value) return;
      
      isDemoSpinMode.value = true;
      cancelAnimationFrame(idleAnimationFrame);
      isSpinning.value = true;
      isResultMode.value = false;
      
      const trackItems = [];
      for (let i = 0; i < 60; i++) {
        const randomItem = catalogItems.value[Math.floor(Math.random() * catalogItems.value.length)];
        trackItems.push({ ...randomItem });
      }
      
      const winnerIndex = Math.floor(Math.random() * catalogItems.value.length);
      const winner = catalogItems.value[winnerIndex];
      trackItems[50] = winner;
      winningItem.value = winner;
      displayItems.value = trackItems;

      performSpinAnimation(50);
    };

    const resetCase = () => {
      if (!winningItem.value) return;

      const winner = winningItem.value;
      isResultMode.value = false;
      isSpinning.value = false;
      winningItem.value = null;
      transitionTime.value = 0;
      
      // Находим индекс в оригинальном каталоге по sticker_id (так как в выигрыше может быть uuid)
      const baseIndex = catalogItems.value.findIndex(item => item.sticker_id === winner.sticker_id);
      
      const newDisplayItems = [...catalogItems.value, ...catalogItems.value, ...catalogItems.value, ...catalogItems.value, ...catalogItems.value, ...catalogItems.value];
      const targetIndexInNewList = catalogItems.value.length * 2 + baseIndex;
      
      displayItems.value = newDisplayItems;
      offset.value = -(targetIndexInNewList * step + 95);
      
      startIdleAnimation();

      // Если за это время пришел сигнал о неактивности кейса — уходим на главную
      if (pendingInactivityRedirect.value) {
        router.push('/');
      }
    };

    const playingLottieId = ref(null);
    const lottieContainers = ref({}); 
    let activeLottieInstances = {};

    const getAnimationType = (item) => {
      if (!item.lottie_url) return null;
      const url = item.lottie_url.toLowerCase();
      if (url.endsWith('.webm')) return 'webm';
      if (url.endsWith('.tgs')) return 'tgs';
      if (url.endsWith('.json')) return 'lottie';
      return null;
    };

    const playCatalogLottie = async (item) => {
      const animType = getAnimationType(item);
      if (!animType || !item.lottie_url) return;

      if (animType === 'lottie' && activeLottieInstances[item.id]) {
        activeLottieInstances[item.id].goToAndPlay(0, true);
        return;
      }

      playingLottieId.value = item.id;
      await nextTick();

      if (animType === 'lottie') {
        const container = lottieContainers.value[item.id];
        if (container) {
          const instance = lottie.loadAnimation({
            container: container,
            renderer: 'svg',
            loop: false,
            autoplay: true,
            path: item.lottie_url,
            rendererSettings: {
              preserveAspectRatio: 'xMidYMid meet'
            }
          });

          activeLottieInstances[item.id] = instance;

          instance.onComplete = () => {
            instance.destroy();
            delete activeLottieInstances[item.id];
            playingLottieId.value = null;
          };
        }
      } else if (animType === 'tgs') {
        setTimeout(() => stopAnimation(item.id), 3000);
      }
    };

    const stopAnimation = (id) => {
      if (activeLottieInstances[id]) {
        activeLottieInstances[id].destroy();
        delete activeLottieInstances[id];
      }
      playingLottieId.value = null;
    };

    const trackStyle = computed(() => ({
      transform: `translateX(${offset.value}px)`,
      transition: transitionTime.value > 0 
        ? `transform ${transitionTime.value}s cubic-bezier(0.15, 0, 0.15, 1)` 
        : 'none'
    }));

    const centeredIndex = computed(() => {
      const i = Math.round((-offset.value - 95) / step);
      return i;
    });

    const getCardStyle = (index) => {
      const cardCenter = index * step + 95; 
      const distToCenter = Math.abs(offset.value + cardCenter);
      const factor = Math.pow(Math.max(0, 1 - distToCenter / step), 3);
      
      const scale = 0.8 + (1 - 0.8) * factor;
      const opacity = 0.5 + (1 - 0.5) * factor;
      
      return {
        transform: `scale(${scale})`,
        opacity: opacity,
        transition: transitionTime.value > 0 ? `all 0.4s ease` : 'none',
        zIndex: factor > 0.1 ? 5 : 1
      };
    };

    const getStickerStyle = (index) => {
      const cardCenter = index * step + 95;
      const distToCenter = Math.abs(offset.value + cardCenter);
      const factor = Math.pow(Math.max(0, 1 - distToCenter / step), 3);
      const size = 125 + (120 - 125) * factor;
      
      return {
        width: `${size}px`,
        height: `${size}px`,
        transition: transitionTime.value > 0 ? `all 0.4s ease` : 'none'
      };
    };

    let idleAnimationFrame;
    const startIdleAnimation = () => {
      if (isSpinning.value || isResultMode.value || !catalogItems.value.length) return;
      offset.value -= 1; 
      const cycleLength = catalogItems.value.length * step;
      if (Math.abs(offset.value - initialOffset) >= cycleLength) {
        offset.value += cycleLength;
      }
      idleAnimationFrame = requestAnimationFrame(startIdleAnimation);
    };

    onMounted(() => {
      fetchCaseData();
      
      // Слушаем обновления кейса через кастомное событие
      const handleCaseUpdate = (event) => {
        if (event.detail.case_slug === route.params.slug && currentCase.value) {
          if (event.detail.is_active !== undefined) {
            currentCase.value.is_active = event.detail.is_active;
            
            // Если кейс стал неактивным
            if (!event.detail.is_active) {
              // Если мы НЕ крутим и НЕ смотрим результат — уходим сразу
              if (!isSpinning.value && !isResultMode.value && !isAwaitingResult.value) {
                router.push('/');
              } else {
                // Иначе ставим флаг, чтобы уйти после завершения действий
                pendingInactivityRedirect.value = true;
              }
            }
          }
          if (event.detail.price_ton !== undefined) {
            currentCase.value.price_ton = event.detail.price_ton;
          }
          if (event.detail.price_stars !== undefined) {
            currentCase.value.price_stars = event.detail.price_stars;
          }
        }
      };
      
      window.addEventListener('ws:case_status_update', handleCaseUpdate);
      window.caseUpdateHandler = handleCaseUpdate;
    });

    onUnmounted(() => {
      cancelAnimationFrame(idleAnimationFrame);
      if (window.caseUpdateHandler) {
        window.removeEventListener('ws:case_status_update', window.caseUpdateHandler);
      }
    });

    return {
      currentCase,
      loading,
      displayItems,
      catalogItems,
      isSpinning,
      isResultMode,
      winningItem,
      startRealSpin,
      sellWinningSticker,
      startDemoSpin,
      resetCase,
      playingLottieId,
      lottieContainers,
      playCatalogLottie,
      getAnimationType,
      stopAnimation,
      offset,
      trackStyle,
      centeredIndex,
      getCardStyle,
      getStickerStyle,
      activeCurrency,
      containerBgStyle,
      formatPrice,
      formatChance
    };
  }
}
</script>

<style scoped>
.case-contain-section {
  margin-top: 20px;
  background: linear-gradient(66.50deg, rgba(32, 30, 41, 1) 11.94%, rgba(40, 37, 59, 1) 88.06%);
  border-radius: 43px;
  /* Паддинги изменены, чтобы скроллбар был по краям */
  padding: 0; 
  display: flex;
  flex-direction: column;
}

.contain-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding-top: 30px;
}

.contain-icon {
  width: 24px;
  height: 24px;
  object-fit: contain;
}

.contain-title {
  font-size: 19px;
  font-weight: 600;
  color: #FFFFFF;
  margin: 0;
}

.catalog-scroll-wrapper {
  width: 100%;
  padding: 0 20px 20px 20px;
  box-sizing: border-box;
  margin-top: 30px; /* Слайдер начинается ниже на 30 пикселей */
}

.catalog-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(90px, 1fr));
  gap: 20px;
  width: 100%;
}

.catalog-item {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
}

.chance-badge {
  position: absolute;
  top: 0;
  right: 0;
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(4px);
  padding: 2.9px 4.5px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.5);
  z-index: 2;
  white-space: nowrap;
}

.sticker-container {
  width: 100%;
  aspect-ratio: 1 / 1;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.catalog-animation-container {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.catalog-animation-container :deep(svg) {
  width: 100% !important;
  height: 100% !important;
  max-width: 100%;
  max-height: 100%;
}

.catalog-video {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.catalog-sticker-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.price-badge {
  margin-top: 3px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 1000px; /* Бордер радиус 1000 */
  padding: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-width: fit-content;
}

.price-icon {
  width: 12px;
  height: 12px;
  object-fit: contain;
}

.price-text {
  font-size: 13px;
  font-weight: 600;
  color: #FFFFFF;
}

.case-actions {
  display: flex;
  flex-direction: column;
  gap: 15px;
  width: 100%;
  margin-top: 15px; /* Небольшой отступ от предыдущей секции */
  min-height: 125px; /* Чтобы не прыгала высота при исчезновении кнопок */
}

.actions-group {
  display: flex;
  flex-direction: column;
  gap: 15px;
  width: 100%;
}

/* Анимация кнопок */
.button-pop-enter-active,
.button-pop-leave-active {
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.button-pop-enter-from,
.button-pop-leave-to {
  opacity: 0;
  transform: scale(0.8);
}

.btn-open-main {
  width: 100%;
  background: #FFFFFF;
  border: none;
  border-radius: 1000px;
  padding: 21px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  transition: transform 0.1s ease;
}

.btn-open-main:active {
  transform: scale(0.98);
}

.btn-text {
  color: #000000;
  font-size: 19px;
  font-weight: 600;
}

.btn-ton-icon {
  width: 17px;
  height: 17px;
  object-fit: contain;
  filter: brightness(0); /* Делает иконку черной */
}

.btn-open-demo {
  width: 100%;
  background: #232323;
  border: none;
  border-radius: 1000px; /* По аналогии с верхней */
  padding: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #FFFFFF;
  font-size: 19px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.1s ease;
}

.btn-open-demo:active {
  transform: scale(0.98);
}

.btn-open-demo.gray {
  background: #232323;
  color: rgba(255, 255, 255, 0.5);
}

.btn-sell {
  width: 100%;
  background: #FFFFFF;
  border: none;
  border-radius: 1000px;
  padding: 21px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  transition: transform 0.1s ease;
}

.btn-sell:active {
  transform: scale(0.98);
}

.case-view {
  display: flex;
  flex-direction: column;
}

.case-content {
  display: flex;
  flex-direction: column;
}

.live-drop-wrapper {
  margin-left: -20px;
  margin-right: -20px;
}

.case-header {
  padding: 0;
}

.case-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: flex-start;
}

.case-icon {
  width: 26.3px;
  height: 26.2px;
  object-fit: contain;
}

.case-title {
  font-size: 21px;
  font-weight: 600;
  color: #FFFFFF;
  margin: 0;
}

.spinner-section {
  position: relative;
  width: calc(100% + 40px); /* Растягиваем на всю ширину */
  margin-left: -20px;
  margin-right: -20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  overflow: hidden; /* Обрезаем только по горизонтали выходящие карточки */
  padding-top: 0;
}

.spinner-pointer {
  position: absolute;
  top: 15px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10;
  width: 24px;
  height: 31px;
  object-fit: contain;
}

.spinner-container {
  width: 100%;
  height: 100%; /* Контейнер на всю высоту секции */
}

.spinner-track-wrapper {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  width: 100%;
  height: 250px; /* Увеличил высоту враппера */
  position: relative;
}

.spinner-track {
  display: flex;
  align-items: center;
  gap: 0; /* Гэп убран */
  position: absolute;
  left: 50%; /* Центр экрана — точка отсчета для трека */
  will-change: transform;
}

.spinner-card {
  flex-shrink: 0;
  width: 190px; /* 120 + 35*2 */
  height: 190px;
  background: var(--cardBackground, linear-gradient(135.00deg, rgba(61, 61, 61, 1), rgba(46, 46, 46, 1), rgba(30, 29, 29, 1)));
  border-radius: 50px; /* Радиус 50 */
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 15px; /* Фиксированный паддинг 15 */
  box-sizing: border-box;
  opacity: 0.5; 
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  transform: scale(0.8); 
}

.spinner-card.main-card {
  opacity: 1;
  transform: scale(1);
}

.sticker-img {
  width: 100px; /* По умолчанию для вторичных */
  height: 100px;
  object-fit: contain;
  transition: all 0.4s ease;
}

.main-card .sticker-img {
  width: 120px; /* Для основной */
  height: 120px;
}
</style>
