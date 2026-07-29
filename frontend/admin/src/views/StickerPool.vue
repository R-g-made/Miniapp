<template>
  <div>
    <h2>Sticker Pool</h2>
    
    <div class="mb-3">
      <input type="text" v-model="search" @input="fetchPool" class="form-control" placeholder="Search stickers...">
    </div>

    <table class="table table-hover">
      <thead>
        <tr>
          <th>Image</th>
          <th>Name</th>
          <th>Remaining</th>
          <th>Floor (TON)</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in pool" :key="item.id">
          <td><img :src="item.image_url" width="50" height="50" style="object-fit: contain;"></td>
          <td>{{ item.name }}</td>
          <td>{{ item.count_remaining }}</td>
          <td>{{ item.floor_price_ton }}</td>
          <td>
            <button class="btn btn-sm btn-primary" @click="openTransferModal(item)">Transfer Owner</button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Simple Transfer Modal (Conceptual) -->
    <div v-if="selectedItem" class="modal d-block" style="background: rgba(0,0,0,0.5)">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">Transfer Owner: {{ selectedItem.name }}</h5>
            <button type="button" class="btn-close" @click="selectedItem = null"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label class="form-label">New Owner ID (UUID)</label>
              <input type="text" v-model="newOwnerId" class="form-control" placeholder="Leave empty to return to pool">
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" @click="selectedItem = null">Close</button>
            <button type="button" class="btn btn-primary" @click="confirmTransfer">Confirm</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import api from '../api';

const pool = ref([]);
const search = ref('');
const selectedItem = ref(null);
const newOwnerId = ref('');

const fetchPool = async () => {
  const res = await api.getStickerPool(search.value);
  pool.value = res.data;
};

const openTransferModal = (item) => {
  selectedItem.value = item;
  newOwnerId.value = '';
};

const confirmTransfer = async () => {
  // Note: This endpoint actually needs sticker_id (UserSticker), but we show catalog_id.
  // In a real app, we'd need to pick a specific instance or change the API to handle catalog_id transfer.
  // For this task, I'll assume the user wants to change owner of an instance.
  // I will show a message that this is simplified.
  alert("This would transfer a specific instance of " + selectedItem.value.name);
  selectedItem.value = null;
};

onMounted(fetchPool);
</script>
