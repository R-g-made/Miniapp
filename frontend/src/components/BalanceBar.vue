<template>
  <div class="balance-bar-wrapper" :class="(activeCurrency || 'ton').toLowerCase()">
    <!-- Переключатель валют -->
    <div class="currency-switcher">
      <!-- Текущий выбор (индикатор) -->
      <div 
        class="selection-indicator" 
        :style="{ transform: (activeCurrency || 'TON') === 'TON' ? 'translate(0, -50%)' : 'translate(38px, -50%)' }"
      ></div>
      
      <div class="currency-option" :class="{ active: (activeCurrency || 'TON') === 'TON' }" @click="setCurrency('TON')">
        <img src="@/assets/icons/ton.svg" alt="TON" class="icon-svg">
      </div>
      <div class="currency-option" :class="{ active: (activeCurrency || 'TON') === 'STARS' }" @click="setCurrency('STARS')">
        <img src="@/assets/icons/star.svg" alt="STARS" class="icon-svg">
      </div>
    </div>

    <!-- Баланс -->
    <div class="balance-value">
      {{ currentBalance }}
    </div>

    <!-- Кнопка пополнения -->
    <button class="add-funds-btn" @click="$emit('add-funds')">
      <img src="@/assets/icons/plus.svg" alt="Add" class="icon-svg">
    </button>
  </div>
</template>

<script>
import { computed } from 'vue';
import { useAuthStore } from '../store/auth';
import { useAppStore } from '../store/app';

export default {
  name: 'BalanceBar',
  setup() {
    const authStore = useAuthStore();
    const appStore = useAppStore();

    const activeCurrency = computed(() => appStore.activeCurrency);

    const currentBalance = computed(() => {
      const val = activeCurrency.value === 'TON' ? authStore.balanceTon : authStore.balanceStars;
      if (activeCurrency.value === 'STARS') {
        return Math.floor(val || 0);
      }
      return typeof val === 'number' ? val.toFixed(2) : (val || '0.00');
    });

    const setCurrency = (curr) => {
      appStore.setCurrency(curr);
    };

    return {
      activeCurrency,
      currentBalance,
      setCurrency
    };
  }
}
</script>

<style scoped>
.balance-bar-wrapper {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  padding: 5px;
  background-color: #15242C;
  border-radius: 1000px;
  transition: transform 0.1s ease, background-color 0.3s ease;
  height: fit-content;
  cursor: pointer;
}

.balance-bar-wrapper:active {
  transform: scale(0.95);
}

.balance-bar-wrapper.stars {
  background-color: #2C2915;
}

.currency-switcher {
  position: relative;
  display: flex;
  align-items: center;
  gap: 21px;
  padding: 11px 16px;
  background-color: rgba(255, 255, 255, 0.05); /* Белый с 5% прозрачностью */
  border-radius: 1000px;
  cursor: pointer;
  width: 85px; 
  box-sizing: border-box;
}

.selection-indicator {
  position: absolute;
  top: 50%;
  left: 2px; /* Внешний отступ 2px */
  width: 43px;
  height: 34px;
  background-color: rgba(255, 255, 255, 0.1); /* Цвет ffffff с 10% прозрачностью (для индикатора обычно выше) */
  border-radius: 1000px;
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 1;
}

.currency-option {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px; /* Увеличенная область клика */
  height: 100%;
  color: #ffffff;
  transition: color 0.2s;
  cursor: pointer;
}

.icon-svg {
  width: 16px;
  height: 16px;
  object-fit: contain;
}


.balance-value {
  font-family: 'Inter', sans-serif;
  font-weight: 600;
  color: #ffffff;
  font-size: 1.1rem;
  padding: 0 4px;
}

.add-funds-btn {
  width: 38px;
  height: 38px;
  border-radius: 1000px;
  background-color: rgba(255, 255, 255, 0.05); /* Белый с 5% прозрачностью */
  border: none;
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background-color 0.2s;
}
</style>
