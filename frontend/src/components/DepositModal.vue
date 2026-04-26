<template>
  <div class="deposit-modal-root">
    <!-- Затемнение фона -->
    <Transition name="overlay-fade">
      <div v-if="isOpen" class="modal-overlay" @click="closeModal"></div>
    </Transition>

    <!-- Сама модалка -->
    <Transition name="modal-slide">
      <div v-if="isOpen" class="modal-wrapper" @click="closeModal">
        <div class="deposit-modal" @click.stop>
          <!-- Слайдер выбора валюты -->
          <div class="currency-slider-container">
            <div class="currency-slider" @click="toggleCurrency">
              <div 
                class="slider-thumb" 
                :class="{ 'is-ton': activeRefCurrency === 'TON' }"
              ></div>
              <div class="slider-option" :class="{ active: activeRefCurrency === 'STARS' }">
                <img src="@/assets/icons/star.svg" alt="Stars" class="slider-icon">
                <span>Stars</span>
              </div>
              <div class="slider-option" :class="{ active: activeRefCurrency === 'TON' }">
                <img src="@/assets/icons/ton.svg" alt="TON" class="slider-icon">
                <span>TON</span>
              </div>
            </div>
          </div>

          <div class="modal-content">
            <!-- Поле ввода суммы -->
            <div class="input-pill">
              <img 
                :src="activeRefCurrency === 'TON' ? tonIcon : starIcon" 
                alt="Currency" 
                class="input-icon"
              >
              <input 
                type="number" 
                placeholder="Enter amount" 
                class="deposit-input"
                v-model="amount"
              >
            </div>

            <!-- Поле кошелька (только для TON) -->
            <Transition name="fade-slide">
              <div v-if="activeRefCurrency === 'TON'" class="wallet-pill clickable" @click="handleWalletConnect">
                <div class="wallet-left">
                  <img src="@/assets/icons/wallet.svg" alt="Wallet" class="wallet-icon">
                  <span class="wallet-text">{{ walletButtonText }}</span>
                </div>
                <img 
                  :src="isConnected ? plusIcon : arrowIcon" 
                  alt="Action" 
                  class="action-icon"
                  :class="{ 'is-cross': isConnected }"
                >
              </div>
            </Transition>

            <!-- Кнопка Deposit -->
            <button class="deposit-btn" @click="handleDeposit" :disabled="!amount || parseFloat(amount) <= 0">
              Deposit
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue';
import { useAppStore } from '../store/app';
import { storeToRefs } from 'pinia';
import api from '../api/client';
import { initTonConnect, connectWallet, disconnectWallet, checkWalletProof } from '../api/tonConnect';

export default {
  name: 'DepositModal',
  setup() {
    const appStore = useAppStore();
    const isDepositOpen = storeToRefs(appStore).isDepositOpen;
    
    const activeRefCurrency = ref('STARS');
    const amount = ref('');
    const isConnected = ref(false);
    const walletAddress = ref('');
    const isVerifying = ref(false);

    const isOpen = computed(() => isDepositOpen.value);
    
    const closeModal = () => {
      appStore.setDepositOpen(false);
    };

    const toggleCurrency = () => {
      activeRefCurrency.value = activeRefCurrency.value === 'TON' ? 'STARS' : 'TON';
    };

    const walletButtonText = computed(() => {
      if (isVerifying.value) return 'Verifying...';
      if (isConnected.value) {
        return walletAddress.value ? `${walletAddress.value.slice(0, 4)}...${walletAddress.value.slice(-4)}` : 'Connected';
      }
      return 'Connect wallet';
    });

    const handleWalletConnect = async () => {
      if (isConnected.value) {
        await disconnectWallet();
      } else {
        await connectWallet();
      }
    };

    const handleDeposit = async () => {
      if (!amount.value || parseFloat(amount.value) <= 0) return;

      try {
        const response = await api.replenishWallet({
          currency: activeRefCurrency.value,
          amount: parseFloat(amount.value)
        });
        
        const data = response.data;

        if (activeRefCurrency.value === 'TON' && data.ton_transaction) {
          const tc = await initTonConnect();
          
          if (!isConnected.value) {
            // Если кошелек не подключен, сначала просим подключить
            await connectWallet();
            // Прерываем выполнение, так как пользователю нужно время на подключение в модалке
            return;
          }

          const transaction = {
            validUntil: Math.floor(Date.now() / 1000) + 600, // 10 минут
            messages: [
              {
                address: data.ton_transaction.address,
                amount: data.ton_transaction.amount,
                payload: data.ton_transaction.payload
              }
            ]
          };

          console.log('Sending transaction:', transaction);
          
          try {
            const result = await tc.sendTransaction(transaction);
            console.log('Transaction result:', result);
            
            if (result && result.boc) {
              // Отправляем сигнал на бэкенд о том, что транзакция отправлена.
              setTimeout(async () => {
                try {
                  await api.verifyDeposit({
                    amount: parseFloat(amount.value),
                    boc: result.boc
                  });
                } catch (e) {
                  console.warn("Auto-verification pending...", e);
                }
              }, 15000);
              
              window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred('success');
              closeModal();
            }
          } catch (error) {
            console.error('TonConnect sendTransaction error:', error);
            // Можно добавить уведомление пользователю здесь
          }
        } else if (activeRefCurrency.value === 'STARS') {
          // Логика для Telegram Stars (через Telegram.WebApp.openTelegramLink)
          if (data.payment_url) {
            window.Telegram.WebApp.openTelegramLink(data.payment_url);
            closeModal();
          }
        }
      } catch (e) {
        console.error('Deposit failed', e);
      }
    };

    onMounted(async () => {
      const tc = await initTonConnect();
      
      tc.onStatusChange(async (wallet) => {
        console.log('Wallet status changed:', wallet);
        
        if (wallet) {
          const wasConnected = isConnected.value;
          isConnected.value = true;
          walletAddress.value = wallet.account.address;
          console.log('Wallet connected. Address:', wallet.account.address);
          
          // Проверяем наличие Proof
          if (wallet.connectItems?.tonProof) {
            if (wallet.connectItems.tonProof.error) {
              console.error('TonProof error from wallet:', wallet.connectItems.tonProof.error);
              return;
            }
            
            console.log('TonProof received, starting verification on backend...');
            isVerifying.value = true;
            try {
              const success = await checkWalletProof(wallet);
              if (!success) {
                console.error('Wallet verification FAILED on backend');
                await disconnectWallet();
              } else {
                console.log('Wallet successfully VERIFIED and LINKED in DB');
              }
            } catch (e) {
              console.error('Exception during wallet verification:', e);
            } finally {
              isVerifying.value = false;
            }
          } else {
            console.warn('Wallet connected but NO TonProof item found. DB linking skipped.');
            if (!wasConnected) {
              console.info('Tip: Ensure tonConnectUI.setConnectRequestParameters was called with a fresh payload before connecting.');
            }
          }
        } else {
          console.log('Wallet disconnected');
          isConnected.value = false;
          walletAddress.value = '';
          isVerifying.value = false;
        }
      });
    });

    const starIcon = new URL('../assets/icons/star.svg', import.meta.url).href;
    const tonIcon = new URL('../assets/icons/ton.svg', import.meta.url).href;
    const arrowIcon = new URL('../assets/icons/arrow.svg', import.meta.url).href;
    const plusIcon = new URL('../assets/icons/plus.svg', import.meta.url).href;

    return {
      isOpen,
      activeRefCurrency,
      amount,
      isConnected,
      walletAddress,
      isVerifying,
      walletButtonText,
      handleWalletConnect,
      handleDeposit,
      closeModal,
      toggleCurrency,
      starIcon,
      tonIcon,
      arrowIcon,
      plusIcon
    };
  }
}
</script>

<style scoped>
.deposit-modal-root {
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
  pointer-events: none; /* Чтобы клики пролетали сквозь враппер к оверлею */
}

.deposit-modal {
  pointer-events: auto; /* Возвращаем клики самой модалке */
  width: calc(100% - 40px);
  max-width: 500px;
  margin-bottom: calc(20px + env(keyboard-inset-height, 0px));
  background: #171717;
  border-radius: 48px;
  padding: 30px 20px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  transition: margin-bottom 0.3s ease-out;
  will-change: transform;
}

/* Слайдер выбора валюты */
.currency-slider-container {
  display: flex;
  justify-content: center;
  margin-bottom: 30px;
}

.currency-slider {
  width: 212px;
  height: 49px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 1000px;
  position: relative;
  display: flex;
  align-items: center;
  padding: 4px;
  box-sizing: border-box;
  cursor: pointer;
}

.slider-thumb {
  position: absolute;
  width: 102px;
  height: 41px;
  background: #FFFFFF;
  border-radius: 1000px;
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 1;
}

.slider-thumb.is-ton {
  transform: translateX(102px);
}

.slider-option {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  z-index: 2;
  transition: color 0.3s;
  color: rgba(255, 255, 255, 0.3);
}

.slider-option.active {
  color: #000000;
}

.slider-icon {
  width: 13.96px;
  height: 13.96px;
  object-fit: contain;
  filter: brightness(0) invert(1) opacity(0.3);
  transition: filter 0.3s;
}

.active .slider-icon {
  filter: brightness(0);
}

.slider-option span {
  font-size: 15.03px;
  font-weight: 600;
}

/* Контент модалки */
.modal-content {
  display: flex;
  flex-direction: column;
}

.input-pill, .wallet-pill {
  width: 100%;
  background: #2B2B2B;
  border-radius: 1000px;
  padding: 20px;
  display: flex;
  align-items: center;
  box-sizing: border-box;
  transition: transform 0.15s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.input-pill:active {
  transform: scale(0.96);
}

.input-pill:focus-within {
  transform: scale(1.02);
}

.input-pill {
  gap: 19px;
}

.input-icon {
  width: 22px;
  height: 22px;
  opacity: 0.5;
  object-fit: contain;
}

.deposit-input {
  flex: 1;
  background: transparent;
  border: none;
  font-size: 15px;
  font-weight: 500;
  color: #FFFFFF;
  padding: 0;
}

.deposit-input::placeholder {
  color: rgba(255, 255, 255, 0.5);
}

.wallet-pill {
  margin-top: 18px;
  justify-content: space-between;
}

.wallet-left {
  display: flex;
  align-items: center;
  gap: 13px;
}

.wallet-icon {
  width: 22px;
  height: 22px;
  object-fit: contain;
  opacity: 1;
}

.wallet-text {
  font-size: 15px;
  font-weight: 500;
  color: #FFFFFF;
}

.action-icon {
  width: 23.4px;
  height: 14.4px;
  object-fit: contain;
  opacity: 0.5;
  transition: transform 0.3s ease;
}

.action-icon.is-cross {
  transform: rotate(45deg);
}

.deposit-btn {
  width: 100%;
  background: #FFFFFF;
  border: none;
  border-radius: 1000px;
  margin-top: 54px;
  padding: 21px;
  font-size: 19px;
  font-weight: 600;
  color: #000000;
  cursor: pointer;
  transition: transform 0.1s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.deposit-btn:active {
  transform: scale(0.98);
}

.clickable {
  cursor: pointer;
}

.clickable:active {
  opacity: 0.8;
}

/* Анимации */
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
  transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

.modal-slide-enter-from,
.modal-slide-leave-to {
  transform: translateY(120%);
}

.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.15s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.fade-slide-enter-from,
.fade-slide-leave-to {
  opacity: 0;
  transform: scale(0.8);
}
</style>
