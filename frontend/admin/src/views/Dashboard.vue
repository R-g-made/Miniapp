<template>
  <div>
    <h2>Dashboard</h2>
    
    <!-- Период для общей статистики -->
    <div class="mb-3 d-flex gap-2 align-items-center">
      <span class="fw-bold">Stats Period:</span>
      <button @click="fetchStats('today')" class="btn btn-sm btn-outline-primary" :class="{active: statsFilter === 'today'}">Today</button>
      <button @click="fetchStats('all_time')" class="btn btn-sm btn-outline-primary" :class="{active: statsFilter === 'all_time'}">All Time</button>
      <input type="date" v-model="statsDate" @change="fetchStats('date')" class="form-control form-control-sm w-auto">
      <span class="badge bg-secondary ms-2" v-if="stats">{{ stats.period_label }}</span>
    </div>

    <div class="row mb-4" v-if="stats">
      <div class="col-md-3">
        <div class="card text-white bg-primary mb-3">
          <div class="card-body">
            <h5 class="card-title">Dropped Items</h5>
            <p class="card-text fs-2">{{ stats.total_dropped_items }}</p>
          </div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="card text-white bg-success mb-3">
          <div class="card-body">
            <h5 class="card-title">Floor Value (TON)</h5>
            <p class="card-text fs-2">{{ stats.total_floor_price_ton.toFixed(2) }}</p>
          </div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="card text-white bg-info mb-3">
          <div class="card-body">
            <h5 class="card-title">Total Spent (TON)</h5>
            <p class="card-text fs-2">{{ stats.total_spent_ton.toFixed(2) }}</p>
          </div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="card text-white bg-warning mb-3">
          <div class="card-body">
            <h5 class="card-title">Total Spent (Stars)</h5>
            <p class="card-text fs-2">{{ stats.total_spent_stars }}</p>
          </div>
        </div>
      </div>
    </div>

    <h3>Top Drops</h3>
    <div class="mb-3 d-flex gap-2">
      <button @click="fetchTopDrops('today')" class="btn btn-outline-secondary" :class="{active: filter === 'today'}">Today</button>
      <button @click="fetchTopDrops('all_time')" class="btn btn-outline-secondary" :class="{active: filter === 'all_time'}">All Time</button>
      <input type="date" v-model="selectedDate" @change="fetchTopDrops('date')" class="form-control w-auto">
    </div>

    <table class="table table-striped">
      <thead>
        <tr>
          <th>Image</th>
          <th>Name</th>
          <th>Player</th>
          <th>Price (TON)</th>
          <th>Date</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="drop in drops" :key="drop.sticker_id">
          <td><img :src="drop.image_url" width="50" height="50" style="object-fit: contain;"></td>
          <td>{{ drop.name }}</td>
          <td>{{ drop.player_name }}</td>
          <td>{{ drop.price_ton }}</td>
          <td>{{ new Date(drop.date).toLocaleString() }}</td>
        </tr>
      </tbody>
    </table>

    <nav v-if="totalPages > 1">
      <ul class="pagination">
        <li class="page-item" :class="{disabled: page === 1}">
          <a class="page-link" href="#" @click.prevent="page--">Previous</a>
        </li>
        <li class="page-item" v-for="p in totalPages" :key="p" :class="{active: p === page}">
          <a class="page-link" href="#" @click.prevent="page = p">{{ p }}</a>
        </li>
        <li class="page-item" :class="{disabled: page === totalPages}">
          <a class="page-link" href="#" @click.prevent="page++">Next</a>
        </li>
      </ul>
    </nav>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue';
import api from '../api';

const stats = ref(null);
const statsFilter = ref('today');
const statsDate = ref('');
const drops = ref([]);
const filter = ref('today');
const selectedDate = ref('');
const page = ref(1);
const totalPages = ref(1);
const size = 10;

const fetchStats = async (f) => {
  if (f) statsFilter.value = f;
  
  const params = {
    all_time: statsFilter.value === 'all_time'
  };
  
  if (statsFilter.value === 'date' && statsDate.value) {
    params.date = statsDate.value;
  }

  const res = await api.getDashboardStats(params);
  stats.value = res.data;
};

const fetchTopDrops = async (f) => {
  if (f) filter.value = f;
  
  const params = {
    page: page.value,
    size: size,
    all_time: filter.value === 'all_time'
  };
  
  if (filter.value === 'date' && selectedDate.value) {
    params.date = selectedDate.value;
  }

  const res = await api.getTopDrops(params);
  drops.value = res.data.items;
  totalPages.value = Math.ceil(res.data.total / size);
};

watch(page, () => fetchTopDrops());

onMounted(() => {
  fetchStats();
  fetchTopDrops();
});
</script>
