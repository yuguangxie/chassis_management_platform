<template>
  <RouterView v-if="route.meta.publicLayout" />
  <AppShell v-else />
</template>
<script setup lang="ts">
import { watchEffect } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from './components/layout/AppShell.vue'
const route = useRoute()

watchEffect(() => {
  document.documentElement.dataset.currentRoute = route.path
})
</script>
