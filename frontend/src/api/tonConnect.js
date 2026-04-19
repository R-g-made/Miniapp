import { TonConnectUI } from '@tonconnect/ui';
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
    if (wallet.connectItems?.tonProof && !wallet.connectItems.tonProof.error) {
        try {
            await apiClient.checkTonProof({
                address: wallet.account.address,
                network: wallet.account.chain,
                publicKey: wallet.account.publicKey,
                proof: wallet.connectItems.tonProof.proof
            });
            return true;
        } catch (e) {
            console.error('Ton Proof check failed', e);
            return false;
        }
    }
    return false;
};
