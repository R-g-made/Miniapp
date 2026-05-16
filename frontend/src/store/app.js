import { defineStore } from 'pinia';
import api from '../api/client';

export const useAppStore = defineStore('app', {
    state: () => ({
        issuers: [],
        sortingOptions: [],
        activeCurrency: 'TON',
        user: {
            balance_ton: 0,
            balance_stars: 0
        },
        liveDrops: [], // История лайв-дропов
        config: {
            maintenance: false,
            min_deposit: 1.0
        },
        initialized: false,
        isNavBarHidden: false,
        isDepositOpen: false,
        cases: [], // Список кейсов с их статусом
        homeFilters: {
            selectedIssuer: null,
            currentSort: 'newer'
        }
    }),
    
    actions: {
        setHomeFilters(filters) {
            this.homeFilters = { ...this.homeFilters, ...filters };
        },
        setDepositOpen(open) {
            this.isDepositOpen = open;
            this.isNavBarHidden = open; // Скрываем навбар при открытом модальном окне
        },
        addLiveDrop(drop) {
            const newDrop = {
                ...drop,
                timestamp: Date.now()
            };
            this.liveDrops.unshift(newDrop);
            if (this.liveDrops.length > 15) {
                this.liveDrops.pop();
            }
        },
        setCases(cases) {
            this.cases = cases;
        },
        updateCaseStatus(caseSlug, isActive, priceTon = null, priceStars = null) {
            const caseIndex = this.cases.findIndex(c => c.slug === caseSlug);
            if (caseIndex !== -1) {
                this.cases[caseIndex].is_active = isActive;
                if (priceTon !== null) {
                    this.cases[caseIndex].price_ton = priceTon;
                }
                if (priceStars !== null) {
                    this.cases[caseIndex].price_stars = priceStars;
                }
            }
        },
        setNavBarHidden(hidden) {
            this.isNavBarHidden = hidden;
        },
        setCurrency(currency) {
            this.activeCurrency = currency;
        },
        updateUser(userData) {
            if (userData) {
                this.user = {
                    ...this.user,
                    ...userData
                };
            }
        },
        async fetchBootstrap() {
            try {
                const response = await api.getBootstrap();
                const data = response.data;
                
                this.issuers = data.dictionaries?.issuers || [];
                this.sortingOptions = data.dictionaries?.sorting_options || [];
                this.config = data.app_config || this.config;
                this.initialized = true;
            } catch (error) {
                console.error("Failed to fetch bootstrap data:", error);
            }
        }
    }
});
