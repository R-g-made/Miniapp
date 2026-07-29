<template>
  <div class="login-container d-flex align-items-center justify-content-center">
    <div class="card p-4 shadow" style="width: 350px;">
      <h3 class="text-center mb-4">Admin Login</h3>
      <div class="mb-3">
        <label class="form-label">Admin Password</label>
        <input type="password" v-model="password" class="form-control" @keyup.enter="handleLogin">
      </div>
      <div v-if="error" class="alert alert-danger p-2 text-center">
        {{ error }}
      </div>
      <button class="btn btn-primary w-100" @click="handleLogin" :disabled="loading">
        {{ loading ? 'Logging in...' : 'Enter' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import api from '../api';

const password = ref('');
const error = ref('');
const loading = ref(false);
const router = useRouter();

const handleLogin = async () => {
  if (!password.value) return;
  
  loading.value = true;
  error.value = '';
  
  try {
    const res = await api.login(password.value);
    localStorage.setItem('admin_token', res.data.token);
    router.push('/');
  } catch (e) {
    error.value = 'Invalid password';
    password.value = '';
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.login-container {
  height: 100vh;
  background-color: #f0f2f5;
}
</style>
