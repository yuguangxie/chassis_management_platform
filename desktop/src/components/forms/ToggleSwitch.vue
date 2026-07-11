<template>
  <button :class="['switch', { on: modelValue }]" @click="$emit('update:modelValue', !modelValue)">
    <span />
  </button>
</template>

<script setup lang="ts">
defineProps({
  modelValue: { type: Boolean, required: true },
})
defineEmits(["update:modelValue"])
</script>

<style scoped>
.switch {
  width: 46px;
  height: 24px;
  border: 1px solid var(--border-subtle);
  background: #22324A;
  border-radius: 999px;
  padding: 2px;
}
.switch span {
  display: block;
  width: 18px;
  height: 18px;
  background: #8AA2C2;
  border-radius: 50%;
  transition: .2s;
}
.switch.on {
  background: #0B5130;
}
.switch.on span {
  transform: translateX(20px);
  background: var(--success);
}
</style>
