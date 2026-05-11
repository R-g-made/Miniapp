import { TonConnectUI, toUserFriendlyAddress } from '@tonconnect/ui';
import apiClient from './client';
import { useAuthStore } from '../store/auth';

let tonConnectUI = null;

export const initTonConnect = async () => {
    if (tonConnectUI) return tonConnectUI;

    const manifestUrl = window.location.origin + '/tonconnect-manifest.json';
    console.log('Initializing TON Connect with manifest:', manifestUrl);

    tonConnectUI = new TonConnectUI({
        manifestUrl: manifestUrl,
        buttonRootId: null
    });

    // Установка Ton Proof из AuthStore
    try {
        const authStore = useAuthStore();
        const payload = authStore.tonProofPayload;
        
        if (payload) {
            tonConnectUI.setConnectRequestParameters({
                state: 'ready',
                value: {
                    tonProof: payload
                }
            });
        }
    } catch (e) {
        console.error('Failed to set Ton Proof payload from store', e);
    }

    return tonConnectUI;
};

export const getTonConnect = () => {
    if (!tonConnectUI) return initTonConnect();
    return tonConnectUI;
};

export const connectWallet = async () => {
    const tc = await getTonConnect();
    
    // Перед открытием модалки запрашиваем свежий payload для Ton Proof
    try {
        const response = await apiClient.getTonProofPayload();
        const payload = response.data.payload;
        
        if (payload) {
            tc.setConnectRequestParameters({
                state: 'ready',
                value: {
                    tonProof: payload
                }
            });
        }
    } catch (e) {
        console.error('Failed to fetch Ton Proof payload before connection', e);
    }

    try {
        await tc.openModal();
    } catch (e) {
        console.error('Wallet connection failed', e);
    }
};

export const disconnectWallet = async () => {
    const tc = await getTonConnect();
    if (tc.connected) {
        await tc.disconnect();
    }
};

export const checkWalletProof = async (wallet) => {
    const authStore = useAuthStore();
    
    // Ожидаем окончания инициализации авторизации (до 2 секунд)
    let retries = 40;
    while (!authStore.initialized && retries > 0) {
        await new Promise(resolve => setTimeout(resolve, 50));
        retries--;
    }

    if (!authStore.isLoggedIn) {
        console.error('[TonConnect] Cannot link wallet: User is not logged in');
        return false;
    }

    const address = wallet.account.address;
    console.log('[TonConnect] checkWalletProof called for:', address);

    // Сравниваем адреса с учетом обоих форматов (Raw и User-Friendly)
    const storedAddress = authStore.user?.wallet_address;
    if (storedAddress) {
        try {
            const friendlyAddress = toUserFriendlyAddress(address);
            const storedFriendly = toUserFriendlyAddress(storedAddress);
            if (friendlyAddress === storedFriendly || storedAddress === address) {
                console.log('[TonConnect] Wallet is already linked in DB, skipping request.');
                return true;
            }
        } catch (e) {
            if (storedAddress === address) return true;
        }
    }

    // 1. Пытаемся через TonProof (безопасный путь)
    if (wallet.connectItems?.tonProof && !wallet.connectItems.tonProof.error) {
        try {
            const proofData = {
                address: address,
                network: wallet.account.chain,
                publicKey: wallet.account.publicKey,
                proof: wallet.connectItems.tonProof.proof
            };
            console.log('[TonConnect] Sending proof to backend:', proofData);
            await apiClient.checkTonProof(proofData);
            
            // Обновляем стор
            const authStore = useAuthStore();
            if (authStore.user) {
                authStore.user.wallet_address = address;
            }
            
            return true;
        } catch (e) {
            console.error('[TonConnect] Backend proof verification failed, falling back to direct link...', e);
        }
    }

    // 2. ФОЛБЭК: Прямая привязка адреса (надежный путь для TMA)
    try {
        console.log('[TonConnect] No proof or proof failed. Linking address directly:', address);
        await apiClient.linkWallet({ address: address });
        console.log('[TonConnect] Direct link successful');
        
        // Обновляем стор
        const authStore = useAuthStore();
        if (authStore.user) {
            authStore.user.wallet_address = address;
        }
        
        return true;
    } catch (e) {
        console.error('[TonConnect] Direct link failed:', e);
        return false;
    }
};
