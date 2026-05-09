<template>
  <div class="inventory-view">
    <!-- Поиск -->
    <div class="search-container">
      <div class="search-wrapper">
        <img src="@/assets/icons/search.svg" alt="Search" class="search-icon">
        <input 
          type="text" 
          v-model="searchQuery" 
          placeholder="Search" 
          class="search-input"
        >
      </div>
    </div>

    <!-- Фильтры эмитентов -->
    <div v-if="issuers && issuers.length" class="issuers-wrapper">
      <div class="issuers-container">
        <div 
          class="issuer-item all" 
          :class="{ active: !selectedIssuer }" 
          @click="selectedIssuer = null"
        >
          All
        </div>
        <div 
          v-for="issuer in issuers" 
          :key="issuer.slug" 
          class="issuer-item" 
          :class="{ active: selectedIssuer === issuer.slug }"
          @click="selectedIssuer = issuer.slug"
        >
          <img v-if="issuer.icon_url" :src="issuer.icon_url" :alt="issuer.name" class="issuer-photo">
          <span class="issuer-name">{{ issuer.name }}</span>
        </div>
      </div>
    </div>

    <!-- Список стикеров -->
    <Transition name="grid-fade" mode="out-in">
      <div v-if="filteredStickers.length > 0" class="stickers-grid" :key="selectedIssuer + searchQuery">
        <TransitionGroup name="sticker-list" appear>
          <div 
            v-for="sticker in filteredStickers" 
            :key="sticker.uuid" 
            class="sticker-card-new" 
            @click="openStickerModal(sticker)"
          >
            <!-- Номер стикера (плашка) -->
            <div class="sticker-badge-ribbon">
              <span class="badge-text">№{{ sticker.number }}</span>
            </div>

            <div class="sticker-image-container">
              <img :src="sticker.image_url" :alt="sticker.name" class="sticker-img">
            </div>
            <h3 class="sticker-name">{{ sticker.name }}</h3>
            
            <div class="sticker-footer">
              <div class="price-pill">
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
                <span class="price-value">{{ formatPrice(sticker) }}</span>
              </div>
              <button class="menu-btn">
                <img src="@/assets/icons/menu.svg" alt="Menu" class="menu-icon">
              </button>
            </div>
          </div>
        </TransitionGroup>
      </div>
      <div v-else class="empty-state">
        <div 
          v-if="filteredStickers.length === 0" 
          class="empty-lottie"
          ref="emptyLottieContainer"
        ></div>
        <p class="empty-text">No stickers found</p>
        <router-link to="/" class="btn-primary-new">Get Packs</router-link>
      </div>
    </Transition>

    <!-- Модалка управления стикером -->
    <Transition name="slide-up">
      <div v-if="selectedSticker" class="modal-overlay" @click="closeStickerModal">
        <div class="modal-content-new" @click.stop>
          <div class="modal-body-new">
            <!-- Контейнер для Lottie -->
            <div class="lottie-container" ref="lottieContainer" @click="replayLottie">
              <video 
                v-if="selectedSticker && getAnimationType(selectedSticker) === 'webm'" 
                :src="selectedSticker.lottie_url" 
                autoplay 
                muted 
                playsinline 
                loop
                class="modal-video"
              ></video>
              <img v-else-if="!lottieEnabled && selectedSticker" :src="selectedSticker.image_url" class="modal-sticker-img">
            </div>
            
            <div class="modal-sticker-title">
              <span class="sticker-main-name">{{ selectedSticker.name }}</span>
              <span class="sticker-main-number">#{{ selectedSticker.number }}</span>
            </div>

            <div class="modal-actions-container">
              <!-- Sell for Active Currency -->
              <div class="action-row" @click="sellSticker(activeCurrency)">
                <img src="@/assets/icons/cart.svg" alt="Cart" class="action-icon cart-icon">
                <span class="action-text">Sell for</span>
                <img 
                  v-if="activeCurrency === 'TON'"
                  src="@/assets/icons/ton.svg" 
                  alt="TON" 
                  class="action-currency-icon"
                >
                <img 
                  v-else
                  src="@/assets/icons/star.svg" 
                  alt="STARS" 
                  class="action-currency-icon"
                >
                <span class="action-price">{{ formatPrice(selectedSticker) }}</span>
                <div class="spacer"></div>
                <img src="@/assets/icons/arrow.svg" alt="Arrow" class="action-arrow">
              </div>

              <!-- Withdraw -->
              <div class="action-row" @click="transferSticker" :style="{ opacity: isTransferring ? 0.5 : 1, pointerEvents: isTransferring ? 'none' : 'auto' }">
                <img src="@/assets/icons/sort-icon.svg" alt="Sort" class="action-icon sort-icon">
                <span class="action-text">{{ isTransferring ? 'Withdrawing...' : 'Withdraw to' }}</span>
                <template v-if="selectedSticker.is_onchain">
                  <img src="@/assets/icons/ton.svg" alt="TON" class="action-issuer-icon">
                  <span class="action-issuer-name">TON</span>
                </template>
                <template v-else>
                  <img src="https://i.ibb.co/MDjJzGVC/Thermos.jpg" alt="Thermos" class="action-issuer-icon thermos-icon">
                  <span class="action-issuer-name">Thermos</span>
                </template>
                <div class="spacer"></div>
                <img src="@/assets/icons/arrow.svg" alt="Arrow" class="action-arrow">
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script>
import { ref, computed, onMounted, nextTick, watch } from 'vue';
import { useAppStore } from '../store/app';
import { useAuthStore } from '../store/auth';
import { storeToRefs } from 'pinia';
import api from '../api/client';
import lottie from 'lottie-web';
import noStickerLottie from '@/assets/icons/Nosticker.json';

export default {
  setup() {
    const appStore = useAppStore();
    const authStore = useAuthStore();
    const { issuers, activeCurrency } = storeToRefs(appStore);

    const stickers = ref([]);
    const selectedSticker = ref(null);
    const isSelling = ref(false);
    const isTransferring = ref(false);
    const searchQuery = ref('');
    const selectedIssuer = ref(null);
    const lottieContainer = ref(null);
    const emptyLottieContainer = ref(null);
    const lottieEnabled = ref(false);
    let lottieInstance = null;
    let emptyLottieInstance = null;

    const filteredStickers = computed(() => {
      return stickers.value.filter(s => {
        const matchesSearch = s.name.toLowerCase().includes(searchQuery.value.toLowerCase()) || 
                              s.number.toString().includes(searchQuery.value);
        const matchesIssuer = !selectedIssuer.value || s.issuer_slug === selectedIssuer.value;
        return matchesSearch && matchesIssuer;
      });
    });

    const getAnimationType = (sticker) => {
      if (!sticker || !sticker.lottie_url) return null;
      const url = sticker.lottie_url.toLowerCase();
      if (url.endsWith('.webm')) return 'webm';
      if (url.endsWith('.tgs')) return 'tgs';
      if (url.endsWith('.json')) return 'lottie';
      return null;
    };

    const openStickerModal = async (sticker) => {
      selectedSticker.value = sticker;
      appStore.setNavBarHidden(true);

      if (lottieInstance) {
        lottieInstance.destroy();
        lottieInstance = null;
      }

      const animType = getAnimationType(sticker);
      
      if (animType === 'lottie' && sticker.lottie_url) {
        lottieEnabled.value = true;
        await nextTick();
        if (lottieContainer.value) {
          lottieInstance = lottie.loadAnimation({
            container: lottieContainer.value,
            renderer: 'svg',
            loop: false,
            autoplay: true,
            path: sticker.lottie_url
          });
        }
      } else {
        lottieEnabled.value = false;
      }
    };

    const closeStickerModal = () => {
      selectedSticker.value = null;
      appStore.setNavBarHidden(false); // Показываем навбар обратно
      
      if (lottieInstance) {
        lottieInstance.destroy();
        lottieInstance = null;
      }
    };

    const replayLottie = () => {
      if (lottieInstance) {
        lottieInstance.goToAndPlay(0, true);
      }
    };

    const formatPrice = (sticker) => {
      if (!sticker) return '0';
      if (activeCurrency.value === 'TON') {
        const val = sticker.floor_price_ton || 0;
        return parseFloat(val).toFixed(2);
      }
      const val = sticker.floor_price_stars || 0;
      return Math.round(parseFloat(val)).toString();
    };

    const fetchStickers = async () => {
      try {
        const response = await api.getMyStickers({
          issuer_slug: selectedIssuer.value
        });
        // Благодаря перехватчику в api/client.js, response.data — это уже объект StickerListData { items, total }
        stickers.value = response.data.items;
      } catch (e) {
        console.error("Fetch stickers failed", e);
      }
    };

    const selectSticker = (sticker) => {
      selectedSticker.value = sticker;
    };

    const sellSticker = async (currency) => {
      isSelling.value = true;
      try {
        const response = await api.sellSticker(selectedSticker.value.id, currency.toLowerCase());
        const newBalance = response.data.new_balance;
        
        // Обновляем баланс в сторе
        authStore.updateBalance(newBalance, currency);
 
        closeStickerModal();
        await fetchStickers(); // Обновляем список
      } catch (e) {
        console.error("Sell failed", e);
        // Если ошибка "Wallet not connected", вызываем привязку кошелька
        if (e.response?.data?.detail?.includes("Wallet not connected") || 
            e.response?.data?.message?.includes("Wallet not connected")) {
          const { connectWallet } = await import('../api/tonConnect');
          connectWallet();
        }
      } finally {
        isSelling.value = false;
      }
    };

    const transferSticker = async () => {
      if (isTransferring.value) return;
      isTransferring.value = true;
      try {
        // Вызываем бэкенд для трансфера. 
        // Бэкенд сам возьмет активный адрес из БД. 
        // Если его нет — вернет 400 "Wallet not connected"
        await api.transferSticker(selectedSticker.value.id);
        closeStickerModal();
        await fetchStickers();
      } catch (e) {
        console.error("Transfer failed", e);
        if (e.response?.data?.detail?.includes("Wallet not connected") || 
            e.response?.data?.message?.includes("Wallet not connected")) {
          const { connectWallet } = await import('../api/tonConnect');
          connectWallet();
        }
      } finally {
        isTransferring.value = false;
      }
    };

    const isLocked = (dateStr) => {
        if (!dateStr) return false;
        return new Date(dateStr) > new Date();
    };

    const formatDate = (dateStr) => {
        return new Date(dateStr).toLocaleDateString();
    };

    const getIssuerIcon = (slug) => {
        const issuer = issuers.value.find(i => i.slug === slug);
        return issuer?.icon_url || '';
    };

    const getIssuerName = (slug) => {
        const issuer = issuers.value.find(i => i.slug === slug);
        return issuer?.name || 'Issuer';
    };

    const initEmptyLottie = async () => {
      await nextTick();
      if (emptyLottieContainer.value && !emptyLottieInstance) {
        emptyLottieInstance = lottie.loadAnimation({
          container: emptyLottieContainer.value,
          renderer: 'svg',
          loop: true,
          autoplay: true,
          animationData: noStickerLottie
        });
      }
    };

    watch(filteredStickers, (newVal) => {
      if (newVal.length === 0) {
        initEmptyLottie();
      } else if (emptyLottieInstance) {
        emptyLottieInstance.destroy();
        emptyLottieInstance = null;
      }
    }, { immediate: true });

    onMounted(async () => {
      await fetchStickers();
      if (filteredStickers.value.length === 0) {
        initEmptyLottie();
      }
    });

    return {
      stickers,
      selectedSticker,
      isSelling,
      isTransferring,
      searchQuery,
      selectedIssuer,
      issuers,
      filteredStickers,
      lottieContainer,
      emptyLottieContainer,
      lottieEnabled,
      getAnimationType,
      openStickerModal,
      closeStickerModal,
      selectSticker,
      sellSticker,
      transferSticker,
      isLocked,
      formatDate,
      getIssuerIcon,
      getIssuerName,
      replayLottie,
      formatPrice,
      activeCurrency
    };
  }
}
</script>

<style scoped>
.inventory-view {
  display: flex;
  flex-direction: column;
  gap: 30px;
}

/* Поиск */
.search-container {
  width: 100%;
}

.search-wrapper {
  background-color: #202020;
  border-radius: 1000px;
  padding: 22px 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: text;
  transition: transform 0.1s ease, background-color 0.2s;
}

.search-wrapper:active {
  transform: scale(0.98); /* Эффект вдавливания для поиска */
}

.search-icon {
  width: 18px;
  height: 18px;
  object-fit: contain;
  opacity: 0.5;
}

.search-input {
  background: transparent;
  border: none;
  outline: none;
  color: #FFFFFF;
  font-size: 16px;
  font-weight: 500;
  width: 100%;
}

.search-input::placeholder {
  color: #FFFFFF;
  opacity: 0.3;
}

/* Эмитенты */
.issuers-wrapper {
  width: 100%;
  overflow-x: auto;
  scrollbar-width: none;
}

.issuers-wrapper::-webkit-scrollbar {
  display: none;
}

.issuers-container {
  display: flex;
  gap: 10px;
  padding-bottom: 5px;
}

.issuer-item {
  display: flex;
  align-items: center;
  background-color: #202020;
  border-radius: 1000px;
  padding: 12px 15px; /* 12 по вертикали, 15 по горизонтали */
  cursor: pointer;
  white-space: nowrap;
  transition: transform 0.1s ease, background-color 0.2s; /* Добавлен переход для transform */
}

.issuer-item:active {
  transform: scale(0.92); /* Эффект вдавливания как на главной */
}

.issuer-item.all {
  padding: 12px 22px;
}

.issuer-item.active {
  background-color: #454545;
}

.issuer-photo {
  width: 25px;
  height: 25px;
  border-radius: 50%;
  margin-right: 6px;
  object-fit: cover;
}

.issuer-name, .issuer-item.all {
  font-size: 18px;
  font-weight: 500;
  color: #FFFFFF;
  line-height: 1;
}

/* Сетка стикеров */
.stickers-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(175px, 1fr)); /* 175 мин размер */
  gap: 10px; /* 10 по вертикали и 10 по горизонтали */
}

/* Анимация всей сетки */
.grid-fade-enter-active,
.grid-fade-leave-active {
  transition: opacity 0.2s ease;
}

.grid-fade-enter-from,
.grid-fade-leave-to {
  opacity: 0;
}

/* Анимация карточек внутри сетки */
.sticker-list-enter-from {
  opacity: 0;
  transform: scale(0.6);
}

.sticker-list-enter-to {
  opacity: 1;
  transform: scale(1);
}

.sticker-list-enter-active {
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.sticker-card-new {
  background-color: #202020;
  border-radius: 35px; /* закругление карточек 35 */
  padding: 10px 13px; /* 10 по вертикали, 13 по горизонтали */
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;
  transition: transform 0.1s;
  position: relative;
  overflow: hidden; /* Чтобы плашка уходила за края */
}

.sticker-card-new:active {
  transform: scale(0.95);
}

.sticker-badge-ribbon {
  position: absolute;
  top: 25px; /* top 25px */
  right: -30px; /* right -30px */
  width: 145px;
  height: 30px;
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  transform: rotate(45deg); 
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}

.badge-text {
  color: #FFFFFF;
  font-size: 17px; /* 17px */
  font-weight: 500; /* 500 жирности */
}

.sticker-image-container {
  width: 117px; /* 117*117 */
  height: 117px;
  margin-bottom: 5px; /* 5px отступ */
  display: flex;
  align-items: center;
  justify-content: center;
}

.sticker-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.sticker-name {
  color: #FFFFFF;
  font-size: 18px; /* 18px */
  font-weight: 500; /* 500 жирности */
  margin: 0 0 15px 0; /* 15px отступ до пилюли */
  text-align: center;
}

.sticker-footer {
  display: flex;
  width: 100%;
  gap: 6px; /* 6 гэп */
  margin-top: auto; /* Прижимает к низу карточки */
}

.price-pill {
  flex: 1; /* Расплывается на доступный контейнер */
  height: 45px; /* 45px высота */
  background: rgba(255, 255, 255, 0.05); /* белый 5% */
  border-radius: 1000px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.price-icon {
  width: 16px; /* иконка 16*16 */
  height: 16px;
  object-fit: contain;
}

.price-value {
  color: #FFFFFF;
  font-size: 17px; /* цены 17 */
  font-weight: 500; /* 500 жирности */
}

.menu-btn {
  width: 45px; /* кнопка 45*45 */
  height: 45px;
  background: rgba(255, 255, 255, 0.05); /* белый 5% */
  border-radius: 1000px;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.menu-icon {
  width: 23.76px; /* 23.76 по горизонтали */
  height: 5.28px; /* 5.28 по вертикали */
  object-fit: contain;
}

/* Empty State */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 42px 20px; /* 60 * 0.7 = 42 */
  gap: 14px; /* 20 * 0.7 = 14 */
}

.empty-lottie {
  width: 150px; 
  height: 150px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-text {
  color: #FFFFFF; /* Белый */
  font-size: 20px;
  font-weight: 500;
}

.btn-primary-new {
  /* Если есть отступ у кнопки, тоже уменьшим */
  margin-top: 0; 
}

.btn-primary-new {
  background-color: #FFFFFF;
  color: #000000;
  padding: 12px 24px;
  border-radius: 1000px;
  font-weight: 600;
  text-decoration: none;
  display: inline-block;
}

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  z-index: 2000;
  padding: 20px; /* Боковые отступы 20px для модалки */
}

.modal-content-new {
  background: #171717;
  border: none;
  border-radius: 50px;
  width: 100%; /* Занимает всю ширину за вычетом паддинга оверлея */
  max-width: 500px;
  margin-bottom: env(safe-area-inset-bottom); /* Только отступ системы, 20px уже есть в паддинге оверлея */
  padding: 22px 15px 15px 15px;
  box-sizing: border-box;
}

.modal-body-new {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.lottie-container {
  width: 138px;
  height: 138px;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-sticker-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.modal-video {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.modal-sticker-title {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 3px; /* 3 пикселя отступ */
  margin-bottom: 36px; /* 36 отступ */
}

.sticker-main-name {
  color: #FFFFFF;
  font-size: 22px; /* 22 */
  font-weight: 500; /* 500 жирность */
}

.sticker-main-number {
  color: rgba(255, 255, 255, 0.5); /* ffffff 50% прозрачность */
  font-size: 22px; /* те же размеры */
  font-weight: 500; /* и жирность */
}

.modal-actions-container {
  width: 100%;
  background: rgba(255, 255, 255, 0.05); /* белый 5% */
  border-radius: 35px; /* закругление 35 */
  display: flex;
  flex-direction: column;
}

.action-row {
  display: flex;
  align-items: center;
  padding: 24px; /* 24 отступ по бокам и по вертикали */
  cursor: pointer;
  transition: transform 0.1s ease, background-color 0.2s;
}

.action-row:active {
  background: rgba(255, 255, 255, 0.02);
  transform: scale(0.98);
}

.action-icon {
  width: 24px; /* 24*24 */
  height: 24px;
  opacity: 0.5; /* ffffff 50% прозрачность */
  margin-right: 12px; /* 12 gap */
}

.action-text {
  color: rgba(255, 255, 255, 0.7); /* ffffff 70% прозрачность */
  font-size: 18px; /* 18 */
  font-weight: 500; /* 500 жирности */
  margin-right: 8px; /* 8 отступ */
}

.action-currency-icon {
  width: 17px; /* 17*17 */
  height: 17px;
  margin-right: 6px; /* 6 отступ */
}

.action-price {
  color: #FFFFFF;
  font-size: 18px;
  font-weight: 500;
}

.action-issuer-icon {
  width: 24px; /* 24*24 иконка иссусиера */
  height: 24px;
  object-fit: cover;
  border-radius: 6px;
  margin-right: 8px;
}

.action-issuer-icon.thermos-icon {
  border-radius: 50%; /* Делаем круглую иконку для Thermos */
}

.action-issuer-name {
  color: #FFFFFF;
  font-size: 18px;
  font-weight: 500;
}

.spacer {
  flex: 1; /* авто-гэп */
}

.action-arrow {
  width: 16px;
  height: 16px;
  opacity: 0.5; /* ffffff 50% прозрачности */
}

/* Анимация появления снизу (slide-up) */
.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.slide-up-enter-active .modal-content-new,
.slide-up-leave-active .modal-content-new {
  transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.slide-up-enter-from,
.slide-up-leave-to {
  opacity: 0;
}

.slide-up-enter-from .modal-content-new,
.slide-up-leave-to .modal-content-new {
  transform: translateY(100%);
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.3s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
