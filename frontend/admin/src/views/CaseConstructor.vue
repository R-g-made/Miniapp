<template>
  <div>
    <h2>Case Constructor</h2>
    
    <div class="row">
      <div class="col-md-6">
        <div class="card p-3 mb-4">
          <h4>Create New Case</h4>
          <div class="mb-3">
            <label class="form-label">Case Name</label>
            <input type="text" v-model="newCase.name" class="form-control">
          </div>
          <div class="mb-3">
            <label class="form-label">Slug (unique-id)</label>
            <input type="text" v-model="newCase.slug" class="form-control">
          </div>
          <div class="mb-3">
            <label class="form-label">Price (TON)</label>
            <input type="number" v-model="newCase.price_ton" class="form-control" step="0.1">
          </div>
          <div class="mb-3">
            <label class="form-label">Price (Stars)</label>
            <input type="number" v-model="newCase.price_stars" class="form-control">
          </div>
          <div class="mb-3">
            <label class="form-label">Image URL</label>
            <input type="text" v-model="newCase.image_url" class="form-control">
          </div>
          
          <h5>Selected Items & Weights</h5>
          <div v-for="id in selectedItemIds" :key="id" class="d-flex align-items-center mb-2">
            <span class="flex-grow-1">{{ getItemName(id) }}</span>
            <input type="number" v-model="itemWeights[id]" class="form-control w-25 ms-2" placeholder="Weight">
          </div>

          <button class="btn btn-primary mt-3" @click="saveCase">Create Case</button>
        </div>

        <!-- Block 4.5: Create Catalog Sticker -->
        <div class="card p-3">
          <h4>Create Catalog Sticker</h4>
          <div class="mb-3">
            <label class="form-label">Issuer ID (UUID)</label>
            <input type="text" v-model="newSticker.issuer_id" class="form-control">
          </div>
          <div class="mb-3">
            <label class="form-label">Name</label>
            <input type="text" v-model="newSticker.name" class="form-control">
          </div>
          <div class="mb-3">
            <label class="form-label">Image URL</label>
            <input type="text" v-model="newSticker.image_url" class="form-control">
          </div>
          <button class="btn btn-secondary mt-3" @click="saveSticker">Create Sticker</button>
        </div>
      </div>

      <div class="col-md-6">
        <h4>Full Catalog</h4>
        <div class="mb-3">
          <input type="text" v-model="catalogSearch" class="form-control" placeholder="Search catalog...">
        </div>
        <div style="max-height: 600px; overflow-y: auto;">
          <div v-for="item in filteredCatalog" :key="item.id" class="form-check border-bottom py-2">
            <input class="form-check-input" type="checkbox" :value="item.id" v-model="selectedItemIds">
            <label class="form-check-label d-flex align-items-center">
              <img :src="item.image_url" width="30" height="30" class="me-2">
              {{ item.name }}
            </label>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import api from '../api';

const catalog = ref([]);
const catalogSearch = ref('');
const selectedItemIds = ref([]);
const itemWeights = ref({});

const newCase = ref({
  name: '',
  slug: '',
  price_ton: 0,
  price_stars: 0,
  image_url: '',
  styles: {}
});

const newSticker = ref({
  issuer_id: '',
  name: '',
  image_url: ''
});

const fetchCatalog = async () => {
  const res = await api.getCatalogItems();
  catalog.value = res.data;
};

const filteredCatalog = computed(() => {
  return catalog.value.filter(item => 
    item.name.toLowerCase().includes(catalogSearch.value.toLowerCase())
  );
});

const getItemName = (id) => {
  const item = catalog.value.find(i => i.id === id);
  return item ? item.name : id;
};

const saveCase = async () => {
  const payload = {
    ...newCase.value,
    item_weights: {}
  };
  selectedItemIds.value.forEach(id => {
    payload.item_weights[id] = itemWeights.value[id] || 1;
  });
  
  await api.createCase(payload);
  alert("Case created successfully!");
};

const saveSticker = async () => {
  await api.createCatalogSticker(newSticker.value);
  alert("Sticker created successfully!");
  fetchCatalog();
};

onMounted(fetchCatalog);
</script>
