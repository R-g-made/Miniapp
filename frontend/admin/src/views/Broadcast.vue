<template>
  <div>
    <h2>Bot Broadcast</h2>
    
    <div class="card p-4">
      <div class="mb-3">
        <label class="form-label">Message Text</label>
        <textarea v-model="message" class="form-control" rows="5" placeholder="Enter your broadcast message..."></textarea>
      </div>
      
      <div class="mb-3">
        <label class="form-label">Media URL (Image/Video link)</label>
        <input type="text" v-model="mediaUrl" class="form-control" placeholder="https://example.com/image.jpg">
      </div>

      <div class="alert alert-info">
        Broadcast will be sent to all users who have started the bot.
      </div>

      <button class="btn btn-primary btn-lg" @click="launchBroadcast" :disabled="!message">
        Launch Broadcast
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import api from '../api';

const message = ref('');
const mediaUrl = ref('');

const launchBroadcast = async () => {
  if (confirm("Are you sure you want to start the broadcast to ALL users?")) {
    await api.startBroadcast({
      message: message.value,
      media_url: mediaUrl.value
    });
    alert("Broadcast initiated!");
    message.value = '';
    mediaUrl.value = '';
  }
};
</script>
