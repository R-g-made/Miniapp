<template>
  <div class="admin-layout">
    <nav v-if="!isLoginPage" class="navbar navbar-expand-lg navbar-dark bg-dark mb-4">
      <div class="container-fluid">
        <a class="navbar-brand" href="#">Admin Panel</a>
        <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
          <span class="navbar-toggler-icon"></span>
        </button>
        <div class="collapse navbar-collapse" id="navbarNav">
          <ul class="navbar-nav me-auto">
            <li class="nav-item">
              <router-link class="nav-link" to="/">Dashboard</router-link>
            </li>
            <li class="nav-item">
              <router-link class="nav-link" to="/stickers">Sticker Pool</router-link>
            </li>
            <li class="nav-item">
              <router-link class="nav-link" to="/players">Players</router-link>
            </li>
            <li class="nav-item">
              <router-link class="nav-link" to="/cases">Case Constructor</router-link>
            </li>
            <li class="nav-item">
              <router-link class="nav-link" to="/broadcast">Broadcast</router-link>
            </li>
          </ul>
          <button class="btn btn-outline-light btn-sm" @click="logout">Logout</button>
        </div>
      </div>
    </nav>
    <div :class="{'container': !isLoginPage}">
      <router-view></router-view>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';

const route = useRoute();
const router = useRouter();

const isLoginPage = computed(() => route.path === '/login');

const logout = () => {
  localStorage.removeItem('admin_token');
  router.push('/login');
};
</script>

<style>
.admin-layout {
  min-height: 100vh;
  background-color: #f8f9fa;
}
.nav-link.router-link-active {
  font-weight: bold;
  color: #fff !important;
}
</style>
