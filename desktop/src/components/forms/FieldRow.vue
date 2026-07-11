<template>
  <label class="row">
    <span>{{ label }}</span>
    <slot />
  </label>
</template>

<script setup lang="ts">
defineProps({
  label: { type: String, required: true },
})
</script>

<style scoped>
.row {
  display: grid;
  grid-template-columns: 150px 1fr;
  gap: 10px;
  align-items: center;
  margin-bottom: 10px;
}
.row span {
  color: var(--text-secondary);
}
</style>
