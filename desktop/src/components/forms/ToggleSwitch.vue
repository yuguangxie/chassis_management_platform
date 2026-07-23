<template>
  <button
    class="switch"
    :class="{ on: modelValue }"
    type="button"
    role="switch"
    :aria-checked="modelValue"
    :aria-disabled="disabled"
    :disabled="disabled"
    :title="disabledReason || label"
    :aria-label="label"
    @click="$emit('update:modelValue', !modelValue)"
  >
    <span />
  </button>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  modelValue: boolean
  disabled?: boolean
  label?: string
  disabledReason?: string
}>(), {
  disabled: false,
  label: '开关',
  disabledReason: '',
})
defineEmits<{ 'update:modelValue': [value: boolean] }>()
</script>

<style scoped>
.switch {
  width: 46px;
  height: 24px;
  border: 1px solid var(--border-subtle);
  background: #22324A;
  border-radius: 999px;
  padding: 2px;
  cursor: pointer;
  transition: filter 160ms ease, border-color 160ms ease, box-shadow 160ms ease;
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
.switch:not(:disabled):hover{filter:brightness(1.2);border-color:#75B5FF;box-shadow:0 0 10px rgba(47,128,255,.28)}
.switch:focus-visible{outline:2px solid #9CCBFF;outline-offset:2px}
.switch:disabled{cursor:not-allowed;opacity:.48;filter:saturate(.45)}
</style>
