<template>
  <div class="live-drop-container">
    <!-- Блок LIVE -->
    <div class="live-status-badge">
      <div class="radar-dot"></div>
      <span class="live-text">LIVE</span>
    </div>

    <!-- Список дропов -->
    <div class="drops-scroll">
      <TransitionGroup name="drop-list">
        <div 
          v-for="drop in drops" 
          :key="drop.id || drop.timestamp" 
          class="drop-card"
          :style="{ 
            borderBottom: `4px solid ${getBorderColor(drop.floor_price_ton)}`
          }"
        >
          <img :src="drop.image_url" alt="Drop" class="sticker-img">
        </div>
      </TransitionGroup>
    </div>
  </div>
</template>

<script>
import { computed } from 'vue';
import { useAppStore } from '../store/app';

export default {
  name: 'LiveDrop',
  setup() {
    const appStore = useAppStore();
    const drops = computed(() => appStore.liveDrops);

    const getBorderColor = (price) => {
      // Если цены нет, возвращаем серый (но другой, чтобы отличить от фона)
      if (price === undefined || price === null) return '#555555';
      
      const p = parseFloat(price);
      if (p >= 0 && p < 5) return '#444444';
      if (p >= 5 && p < 15) return '#4B69FE';
      if (p >= 15 && p < 40) return '#B12FC1';
      if (p >= 40) return '#EB4C4B';
      return '#444444';
    };

    return {
      drops,
      getBorderColor
    };
  }
}
</script>

<style scoped>
.live-drop-container {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  padding: 10px 0 20px 0; /* Увеличенный нижний паддинг для бордеров */
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
  box-sizing: border-box;
  background-color: transparent;
  min-height: 130px; /* Используем min-height вместо жесткой height */
}

.live-drop-container::-webkit-scrollbar {
  display: none;
}

.live-status-badge {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background-color: #202020; /* Изменен на 202020 */
  border-radius: 29px;
  min-width: fit-content;
  margin-left: 20px;
  flex-shrink: 0;
  padding: 16px; /* Отступ по вертикали и горизонтали 16px */
  gap: 7px; /* Отступ между точкой и текстом 7px */
}

.radar-dot {
  width: 8px;
  height: 8px;
  background-color: #FF4B4B;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 0 rgba(255, 75, 75, 0.4);
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(255, 75, 75, 0.7); }
  70% { box-shadow: 0 0 0 6px rgba(255, 75, 75, 0); }
  100% { box-shadow: 0 0 0 0 rgba(255, 75, 75, 0); }
}

.live-text {
  font-size: 14px;
  font-weight: 700;
  color: #FFFFFF;
  line-height: 1;
  text-transform: uppercase;
  writing-mode: vertical-rl;
  transform: rotate(180deg); /* Чтобы читалось сверху вниз */
  display: flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
}

.drops-scroll {
  display: flex;
  align-items: center;
  gap: 14px;
  padding-right: 20px;
  position: relative;
  height: 90px; /* С небольшим запасом для бордера */
}

/* Анимации для TransitionGroup */
.drop-list-enter-from {
  opacity: 0;
  transform: scale(0.5); /* Появляется из маленького размера */
}

.drop-list-enter-to {
  opacity: 1;
  transform: scale(1);
}

.drop-list-enter-active {
  transition: all 0.5s cubic-bezier(0.34, 1.56, 0.64, 1); /* Пружинистый эффект */
}

/* Анимация сдвига существующих элементов */
.drop-list-move {
  transition: transform 0.5s ease;
}

/* Плавное исчезновение при удалении лишних */
.drop-list-leave-active {
  transition: all 0.3s ease;
  position: absolute; /* Чтобы не мешать сдвигу других */
  right: 20px; /* Чтобы карточка не улетала за пределы контейнера некрасиво */
}

.drop-list-leave-to {
  opacity: 0;
  transform: translateX(30px);
}

.drop-card {
  flex: 0 0 84.7px; /* flex-grow 0, flex-shrink 0, flex-basis 84.7px */
  width: 84.7px;
  height: 84.7px;
  min-width: 84.7px;
  min-height: 84.7px;
  background-color: #202020; /* Изменен на 202020 */
  border-radius: 29px; /* Закругление 29 */
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 11px;
  box-sizing: border-box;
}

.sticker-img {
  width: 62.7px;
  height: 62.7px;
  object-fit: contain;
  border-radius: 12px;
  flex-shrink: 0;
}
</style>
