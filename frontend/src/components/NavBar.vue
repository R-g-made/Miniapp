<template>
  <nav 
    class="nav-bar" 
    :class="{ 'nav-hidden': isHidden }"
  >
    <!-- Общая подложка для анимации слайда -->
    <div 
      class="active-indicator" 
      :style="indicatorStyle"
    ></div>

    <div 
      v-for="(item, index) in navItems" 
      :key="item.path"
      class="nav-item"
      :class="{ 'active': isActive(item.path) }"
      @click="navigate(item.path)"
    >
      <img 
        :src="item.icon" 
        :alt="item.name" 
        class="nav-icon"
        :style="getIconStyle(item)"
      >
      <span class="nav-text">{{ item.name }}</span>
    </div>
  </nav>
</template>

<script>
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAppStore } from '../store/app';

export default {
  name: 'NavBar',
  setup() {
    const route = useRoute();
    const router = useRouter();
    const appStore = useAppStore();

    const navItems = [
      { 
        name: 'Home', 
        path: '/', 
        icon: new URL('../assets/icons/box-2.svg', import.meta.url).href,
        size: 22
      },
      { 
        name: 'My sticker', 
        path: '/inventory', 
        icon: new URL('../assets/icons/sticker.svg', import.meta.url).href,
        size: 22
      },
      { 
        name: 'Tournament', 
        path: '/tournament', 
        icon: new URL('../assets/icons/trophy.svg', import.meta.url).href,
        size: 22
      },
      { 
        name: 'Profile', 
        path: '/profile', 
        icon: new URL('../assets/icons/profile.svg', import.meta.url).href,
        size: 19
      }
    ];

    const activeIndex = computed(() => {
      const index = navItems.findIndex(item => {
        if (item.path === '/') return route.path === '/';
        return route.path.startsWith(item.path);
      });
      return index !== -1 ? index : 0;
    });

    const isActive = (path) => {
      if (path === '/') return route.path === '/';
      return route.path.startsWith(path);
    };

    const navigate = (path) => {
      if (isActive(path)) {
        // Если уже активен, запускаем анимацию подпружинивания
        if (settleTimeout) clearTimeout(settleTimeout);
        isSettling.value = true;
        settleTimeout = setTimeout(() => {
          isSettling.value = false;
        }, 150);
        return;
      }
      router.push(path);
    };

    const getIconStyle = (item) => ({
      width: `${item.size}px`,
      height: `${item.size}px`,
      opacity: 1
    });

    const isHidden = computed(() => {
      // Скрываем на странице кейса, рефералов или если глобальный флаг в store установлен
      return route.path.startsWith('/case/') || route.path === '/referrals' || appStore.isNavBarHidden;
    });

    // Расчет положения индикатора
    const isMoving = ref(false);
    const isSettling = ref(false);
    let moveTimeout = null;
    let settleTimeout = null;

    const indicatorStyle = computed(() => {
      const itemCount = navItems.length;
      const slotWidth = 100 / itemCount;
      
      let scaleX = 1;
      let scaleY = 1;

      if (isMoving.value) {
        scaleX = 1.15; // Растягивается при движении
        scaleY = 0.95; // Немного приплюскивается
      } else if (isSettling.value) {
        scaleX = 0.95; // Сжимается при "приземлении"
        scaleY = 1.05; // Немного вытягивается вверх
      }
      
      return {
        width: `calc(${slotWidth}% - 2px)`,
        left: `calc(${activeIndex.value * slotWidth}% + 1px)`,
        transform: `scaleX(${scaleX}) scaleY(${scaleY})`
      };
    });

    // Следим за изменением индекса для запуска анимации
    watch(activeIndex, () => {
      isMoving.value = true;
      isSettling.value = false;
      
      if (moveTimeout) clearTimeout(moveTimeout);
      if (settleTimeout) clearTimeout(settleTimeout);

      moveTimeout = setTimeout(() => {
        isMoving.value = false;
        isSettling.value = true;
        
        settleTimeout = setTimeout(() => {
          isSettling.value = false;
        }, 200); // Время на финальное подпружинивание
      }, 300); // Время основного движения
    });

    return {
      navItems,
      isActive,
      navigate,
      getIconStyle,
      indicatorStyle,
      isHidden
    };
  }
}
</script>

<style scoped>
.nav-bar {
  position: fixed;
  bottom: calc(35px + env(safe-area-inset-bottom, 0px));
  left: 15px;
  width: calc(100vw - 30px);
  box-sizing: border-box;
  
  /* Черный 10% и блюр 5px */
  background: rgba(0, 0, 0, 0.1);
  backdrop-filter: blur(5px);
  -webkit-backdrop-filter: blur(5px);
  
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 1000px;
  padding: 15px 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  z-index: 1000;
  
  /* Анимация уплывания */
  transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1), bottom 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.nav-bar.nav-hidden {
  transform: translateY(150%); /* Уплывает вниз за экран */
  bottom: 0;
}

.nav-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3.6px;
  cursor: pointer;
  position: relative;
  z-index: 2;
  transition: transform 0.1s ease;
}

.nav-item:active {
  transform: scale(0.9);
}

.nav-icon {
  object-fit: contain;
  transition: filter 0.3s ease;
  filter: brightness(0) invert(0.6); /* Неактивные иконки серые */
}

.nav-item.active .nav-icon {
  filter: brightness(0) invert(1); /* Активные белые */
}

.nav-text {
  font-size: 12px;
  font-weight: 500;
  color: #8E8E93; /* Неактивный текст серый */
  white-space: nowrap;
  transition: color 0.3s ease;
}

.nav-item.active .nav-text {
  color: #FFFFFF; /* Активный белый */
}

/* Скользящий индикатор */
.active-indicator {
  position: absolute;
  height: calc(100% - 8px);
  
  /* Цвет 414141 с 50% прозрачностью и 5px блюром */
  background: rgba(65, 65, 65, 0.5);
  backdrop-filter: blur(5px);
  -webkit-backdrop-filter: blur(5px);
  
  box-shadow: inset 0 0 10px rgba(255, 255, 255, 0.05);
  
  border-radius: 1000px;
  top: 4px;
  /* Анимация движения и трансформации */
  transition: left 0.3s cubic-bezier(0.4, 0, 0.2, 1), transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 1;
  will-change: transform, left, width;
}
</style>
