<template>
  <div class="home-view">
    <!-- Секция с Live Drop -->
    <div class="live-drop-wrapper">
      <LiveDrop />
    </div>

    <div class="home-content">
      <!-- Заголовок Packs -->
      <div class="packs-header">
        <img src="@/assets/icons/box.svg" alt="Packs" class="packs-icon">
        <h2 class="packs-title">Packs</h2>
      </div>

      <!-- Фильтры и сортировка -->
      <div class="filters-sort-container">
        <!-- Фильтр эмитентов -->
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

        <!-- Кнопка сортировки -->
        <button class="sort-button" @click="toggleSort">
          <span>Sort</span>
          <img src="@/assets/icons/sort-icon.svg" alt="Sort" class="sort-icon">
        </button>
      </div>

      <!-- Сетка кейсов -->
      <Transition name="grid-fade" mode="out-in">
        <div class="cases-grid" :key="(selectedIssuer || 'all') + currentSort">
          <TransitionGroup name="case-list" appear>
            <div 
              v-for="item in cases" 
              :key="item.slug" 
              class="case-card-new" 
              @click="selectCase(item)"
              :style="getCardStyle(item)"
            >
              <div class="case-image-container">
                <img :src="item.image_url" alt="Case" class="case-img">
              </div>
              <h3 class="case-name">{{ item.name }}</h3>
              <div class="case-price-bubble">
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
          </TransitionGroup>
        </div>
      </Transition>
    </div>

    <!-- Окошко сортировки -->
    <Transition name="slide-up">
      <div v-if="isSortOpen" class="modal-overlay" @click="isSortOpen = false">
        <div class="sort-modal" @click.stop>
          <div class="sort-list">
            <div 
              v-for="option in sortingOptions" 
              :key="option.id" 
              class="sort-item"
              :class="{ active: currentSort === option.id }"
              @click="selectSort(option.id)"
            >
              <div v-if="currentSort === option.id" class="sort-active-bg"></div>
              <span class="sort-item-text">{{ option.label }}</span>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import api from '../api/client';
import { useAuthStore } from '../store/auth';
import { useAppStore } from '../store/app';
import { useNotificationStore } from '../store/notification';
import { storeToRefs } from 'pinia';
import LiveDrop from '../components/LiveDrop.vue';

export default {
  components: {
    LiveDrop
  },
  setup() {
    const router = useRouter();
    const authStore = useAuthStore();
    const appStore = useAppStore();
    const notificationStore = useNotificationStore();

    const activeCurrency = computed(() => appStore.activeCurrency);

    const { cases: storeCases, issuers, sortingOptions } = storeToRefs(appStore);
    const selectedIssuer = ref(null);
    const liveDrops = ref([]);
    const selectedCase = ref(null);
    const isOpening = ref(false);
    const dropResult = ref(null);
    
    const cases = computed(() => {
      return storeCases.value.filter(c => c.is_active !== false);
    });
    
    // Сортировка
    const isSortOpen = ref(false);
    
    // Следим за открытием сортировки, чтобы прятать NavBar
    watch(isSortOpen, (val) => {
      appStore.setNavBarHidden(val);
    });

    const currentSort = ref('newer');
    currentSort.value = 'newer';

    const toggleSort = () => {
      isSortOpen.value = !isSortOpen.value;
    };

    const selectSort = (id) => {
      currentSort.value = id;
      // Сохраняем результат и закрываем окошко сразу после нажатия
      setTimeout(() => {
        isSortOpen.value = false;
      }, 100);
      fetchCases();
    };

    const formatPrice = (item) => {
      if (activeCurrency.value === 'STARS') {
        const val = item.price_stars || (item.price_ton * 50);
        return Math.round(parseFloat(val)).toString();
      }
      return parseFloat(item.price_ton || 0).toFixed(2);
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

    const getCardStyle = (item) => {
      const gradient = buildGradient(item.styles, "card_border");
      
      if (gradient) {
        return {
          borderBottom: '4px solid transparent',
          backgroundImage: `linear-gradient(135deg, #2e2e2e 50%, #1e1d1d 100%), ${gradient}`,
          backgroundOrigin: 'padding-box, border-box',
          backgroundClip: 'padding-box, border-box'
        };
      }
      // Иначе используем обычный цвет или серый по умолчанию
      return {
        borderBottom: `4px solid #444444`
      };
    };

    const fetchCases = async () => {
      try {
        const response = await api.getCases({
          issuer_slug: selectedIssuer.value,
          sort_by: currentSort.value
        });
        // Благодаря перехватчику в api/client.js, response.data — это уже массив кейсов
        appStore.setCases(response.data);
      } catch (e) {
        console.error("Fetch cases failed", e);
      }
    };

    // Следим за фильтрами
    watch(selectedIssuer, () => {
      fetchCases();
    });

    const selectCase = (item) => {
      router.push({ 
        name: 'CaseView', 
        params: { slug: item.slug },
        query: { name: item.name }
      });
    };

    const openCase = async (currency) => {
      if (isOpening.value) return;
      isOpening.value = true;
      try {
        const response = await api.openCase(selectedCase.value.slug, currency.toLowerCase());
        dropResult.value = response.data.drop;
        selectedCase.value = null;
        
        // Обновляем баланс в сторе
        authStore.updateBalance(response.data.new_balance, currency);
      } catch (e) {
        // Убрали вызов notificationStore.error(), так как axios interceptor уже показал уведомление
        console.error("Open case failed", e);
      } finally {
        isOpening.value = false;
      }
    };

    // Слушаем Live Drop через кастомное событие из websocket.js
    const handleLiveDrop = (event) => {
      liveDrops.value.unshift(event.detail);
      if (liveDrops.value.length > 10) liveDrops.value.pop();
    };

    onMounted(() => {
      fetchCases();
      window.addEventListener('ws:live_drop', handleLiveDrop);
    });

    onUnmounted(() => {
      window.removeEventListener('ws:live_drop', handleLiveDrop);
      appStore.setNavBarHidden(false); // Сбрасываем при уходе со страницы
    });

    return {
      cases,
      liveDrops,
      selectedCase,
      isOpening,
      dropResult,
      selectCase,
      openCase,
      issuers,
      selectedIssuer,
      toggleSort,
      isSortOpen,
      currentSort,
      sortingOptions,
      selectSort,
      formatPrice,
      activeCurrency,
      getCardStyle
    };
  }
}
</script>

<style scoped>
.home-view {
  display: flex;
  flex-direction: column;
  gap: 20px; /* Уменьшен гэп с 30 до 20 */
}

.home-content {
  display: flex;
  flex-direction: column;
  gap: 20px; /* Уменьшен гэп с 30 до 20 */
}

.filters-sort-container {
  display: flex;
  flex-direction: column;
  gap: 15px; /* Уменьшен гэп с 20 до 15 */
}

.live-drop-wrapper {
  margin-left: -20px;
  margin-right: -20px;
  padding: 5px 0; /* Добавляем внутренний отступ, чтобы бордеры не обрезались */
  overflow: visible;
  position: relative;
  z-index: 1; /* Чтобы лайв-дроп был выше основного контента при скролле */
}

.issuers-wrapper {
  margin-left: -20px;
  margin-right: -20px;
  overflow-x: auto;
  scrollbar-width: none;
}

.issuers-wrapper::-webkit-scrollbar {
  display: none;
}

.issuers-container {
  display: flex;
  gap: 8px;
  padding: 0 20px;
  width: max-content;
}

.issuer-item {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px 15px;
  background-color: #202020;
  border-radius: 1000px; /* Чтобы выглядело как капсула */
  cursor: pointer;
  transition: transform 0.1s ease, background-color 0.2s; /* Добавлена анимация трансформации */
  flex-shrink: 0;
}

.issuer-item:active {
  transform: scale(0.92); /* Эффект вдавливания */
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

.packs-header {
  display: flex;
  align-items: center;
  justify-content: flex-start; /* Прижаты к левому боку */
  gap: 10px;
  width: 100%; /* Растягивание по контейнеру главной страницы */
}


.packs-icon {
  width: 26.3px;
  height: 26.2px;
  object-fit: contain;
}

.packs-title {
  font-size: 21px;
  font-weight: 600;
  color: #FFFFFF;
  margin: 0;
}

.sort-button {
  width: 100%;
  background-color: #202020;
  border: none;
  border-radius: 1000px;
  padding: 18px 0; /* Отступ 18px по вертикали */
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px; /* Отступ от иконки 12 пикселей */
  cursor: pointer;
  transition: transform 0.1s ease, background-color 0.2s;
}

.sort-button:active {
  transform: scale(0.95); /* Эффект вдавливания */
}

.sort-button span {
  font-size: 18px; /* 18 пикселей */
  font-weight: 600; /* 600 жирности */
  color: #FFFFFF;
}

.sort-icon {
  width: 17px; /* 17*17 */
  height: 17px;
  object-fit: contain;
}


.cases-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(175px, 1fr));
  gap: 15px; /* 15 по вертикали и 15 по горизонтали */
  margin-left: -20px;
  margin-right: -20px;
  padding: 0 20px;
}

/* Анимация всей сетки (исчезновение/появление) */
.grid-fade-enter-active,
.grid-fade-leave-active {
  transition: opacity 0.2s ease;
}

.grid-fade-enter-from,
.grid-fade-leave-to {
  opacity: 0;
}

/* Анимации для карточек внутри сетки */
.case-list-enter-from {
  opacity: 0;
  transform: scale(0.6);
}

.case-list-enter-to {
  opacity: 1;
  transform: scale(1);
}

.case-list-enter-active {
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.case-card-new {
  background: linear-gradient(135.00deg, rgba(46, 46, 46, 1) 50.037%,rgba(30, 29, 29, 1) 100.037%);
  border-radius: 30px; /* Закругление 30 */
  padding: 15px 25px; /* 25 по горизонтали, 15 по вертикали */
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px; /* Отступ между элементами карточки 6px */
  cursor: pointer;
  transition: transform 0.2s;
  box-sizing: border-box;
}

.case-card-new:active {
  transform: scale(0.98);
}

.case-image-container {
  width: 125px;
  height: 125px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.case-img {
  width: 125px;
  height: 125px;
  object-fit: contain;
}

.case-name {
  font-size: 20px;
  font-weight: 700;
  color: #FFFFFF;
  margin: 0;
  text-align: center;
}

.case-price-bubble {
  background-color: rgba(255, 255, 255, 0.1); /* Цвет ffffff 10% прозрачности */
  border-radius: 1000px;
  padding: 10px 10px; /* 10 по вертикали и 10 по горизонтали */
  display: flex;
  align-items: center;
  gap: 5px; /* Отступ 5px в пузыре */
  width: fit-content;
}

.price-icon {
  width: 15px;
  height: 14px;
  object-fit: contain;
}

.price-text {
  font-size: 17px;
  font-weight: 600;
  color: #FFFFFF;
}

.case-card {
  cursor: pointer;
  transition: transform 0.2s;
}

/* Модалки и оверлей */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.7); /* Затемнение экрана */
  z-index: 1000;
  display: flex;
  flex-direction: column;
  justify-content: flex-end; /* Окошко снизу */
  align-items: center;
  padding: 0 20px; /* 20px отступы от боков по правилу главного экрана */
  box-sizing: border-box;
}

.sort-modal {
  background-color: #202020; /* Изменен на 202020 */
  border-radius: 50px; /* Закругление модалки 50 */
  padding: 20px;
  width: 100%;
  max-width: 500px; /* Максимальная ширина 500 пикселей */
  margin-bottom: calc(20px + env(safe-area-inset-bottom)); /* 20px + safezone tg снизу */
  box-sizing: border-box;
}

.sort-list {
  display: flex;
  flex-direction: column;
  gap: 10px; /* Отступы(gap)между текстами 10px */
}

.sort-item {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0; /* У текста в сортировке нет падингов */
  width: 100%;
  height: 56px; /* Высота элемента совпадает с высотой выбора для центрирования текста */
}

.sort-item-text {
  font-size: 18px;
  font-weight: 600;
  position: relative;
  z-index: 2;
  color: rgba(255, 255, 255, 0.5); /* ffffff 50% по умолчанию */
  transition: color 0.2s;
}

.sort-item.active .sort-item-text {
  color: #FFFFFF; /* ffffff 100% для выбранного */
}

.sort-active-bg {
  position: absolute;
  top: 50%;
  left: -10px; /* Чтобы разливалось на контейнер с 10px отступами от краев модалки (20-10=10) */
  right: -10px;
  transform: translateY(-50%);
  height: 56px; /* Высота прямоугольника выбора 56px */
  background-color: rgba(255, 255, 255, 0.1); /* Белый ffffff c 10% прозрачностью */
  border-radius: 1000px;
  z-index: 1;
}

/* Анимация появления снизу */
.slide-up-enter-active,
.slide-up-leave-active {
  transition: opacity 0.3s ease;
}

.slide-up-enter-active .sort-modal,
.slide-up-leave-active .sort-modal {
  transition: transform 0.3s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
  opacity: 0;
}

.slide-up-enter-from .sort-modal,
.slide-up-leave-to .sort-modal {
  transform: translateY(100%);
}

.case-card:active {
  transform: scale(0.95);
}
.case-img-wrapper img {
  max-height: 100px;
}
.live-drop-container {
  height: 60px;
  background: rgba(0,0,0,0.05);
  border-radius: 12px;
}
.drop-item img {
  height: 44px;
  width: 44px;
  object-fit: cover;
}
</style>
