<template>
  <div v-if="open" class="dialog">
    <slot />
    <button class="btn primary" @click="$emit('confirm')">确认</button>
  </div>
</template>

<script setup lang="ts">
defineProps({
  open: { type: Boolean, required: true },
})
defineEmits(["confirm"])
</script>

<style scoped>
.dialog {
  position: fixed;
  inset: 30% auto auto 40%;
  background: var(--bg-card-elevated);
  border: 1px solid var(--border-subtle);
  padding: 18px;
  border-radius: 8px;
  z-index: 10;
}
</style>
