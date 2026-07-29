<template>
  <div>
    <h2>Player Management</h2>
    
    <div class="mb-3">
      <input type="text" v-model="search" @input="fetchUsers" class="form-control" placeholder="Search by username, full name or TG ID...">
    </div>

    <table class="table table-hover">
      <thead>
        <tr>
          <th>TG ID</th>
          <th>Username</th>
          <th>Full Name</th>
          <th>Balance (TON)</th>
          <th>Balance (Stars)</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="user in users" :key="user.id">
          <td>{{ user.telegram_id }}</td>
          <td>{{ user.username || '-' }}</td>
          <td>{{ user.full_name || '-' }}</td>
          <td>{{ user.balance_ton.toFixed(2) }}</td>
          <td>{{ user.balance_stars }}</td>
          <td>
            <div class="btn-group">
              <button class="btn btn-sm btn-danger" @click="resetBalance(user.id)">Reset</button>
              <button class="btn btn-sm btn-success" @click="openAdjustModal(user)">Adjust</button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Adjust Balance Modal -->
    <div v-if="selectedUser" class="modal d-block" style="background: rgba(0,0,0,0.5)">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">Adjust Balance: {{ selectedUser.username || selectedUser.telegram_id }}</h5>
            <button type="button" class="btn-close" @click="selectedUser = null"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label class="form-label">Add TON (use negative to subtract)</label>
              <input type="number" v-model="adjustTon" class="form-control" step="0.1">
            </div>
            <div class="mb-3">
              <label class="form-label">Add Stars (use negative to subtract)</label>
              <input type="number" v-model="adjustStars" class="form-control">
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" @click="selectedUser = null">Close</button>
            <button type="button" class="btn btn-primary" @click="confirmAdjust">Apply</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import api from '../api';

const users = ref([]);
const search = ref('');
const selectedUser = ref(null);
const adjustTon = ref(0);
const adjustStars = ref(0);

const fetchUsers = async () => {
  const res = await api.getUsers(search.value);
  users.value = res.data;
};

const resetBalance = async (userId) => {
  if (confirm("Are you sure you want to reset this user's balance to 0?")) {
    await api.resetUserBalance(userId);
    fetchUsers();
  }
};

const openAdjustModal = (user) => {
  selectedUser.value = user;
  adjustTon.value = 0;
  adjustStars.value = 0;
};

const confirmAdjust = async () => {
  await api.adjustUserBalance(selectedUser.value.id, adjustTon.value, adjustStars.value);
  selectedUser.value = null;
  fetchUsers();
};

onMounted(fetchUsers);
</script>
