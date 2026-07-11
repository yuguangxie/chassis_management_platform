<template>
  <section class="card">
    <header v-if="title || $slots.actions">
      <h3>{{ title }}</h3>
      <slot name="actions" />
    </header>
    <slot />
  </section>
</template>

<script setup lang="ts">
defineProps({
  title: { type: String, default: "" },
})
</script>

<style scoped>
.card {
  background: linear-gradient(180deg, var(--bg-card), #0A1A2D);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, .22);
  padding: 14px;
  min-height: 0;
}
header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-subtle);
  padding-bottom: 10px;
  margin-bottom: 12px;
}
h3 {
  font-size: 16px;
  margin: 0;
}
</style>
