<template>
  <IndustrialCard>
    <div class="metric-card">
      <component :is="icon" v-if="icon" :size="28" />
      <div>
        <span>{{ title }}</span>
        <strong class="metric">{{ value }}</strong>
        <em>{{ unit }}</em>
      </div>
    </div>
  </IndustrialCard>
</template>

<script setup lang="ts">
import IndustrialCard from "./IndustrialCard.vue"

defineProps({
  title: { type: String, required: true },
  value: { type: [String, Number], required: true },
  unit: { type: String, default: "" },
  icon: { type: [Object, Function], default: undefined },
})
</script>

<style scoped>
.metric-card {
  display: flex;
  align-items: center;
  gap: 16px;
}
.metric-card svg {
  color: var(--primary);
  background: #0B2340;
  border-radius: 8px;
  padding: 5px;
}
.metric-card span {
  display: block;
  color: var(--text-secondary);
  font-size: 13px;
}
.metric-card strong {
  font-size: 32px;
  line-height: 1.1;
}
.metric-card em {
  font-style: normal;
  color: var(--text-secondary);
  margin-left: 5px;
}
</style>
