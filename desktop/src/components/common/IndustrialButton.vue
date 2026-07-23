<template>
  <button
    class="industrial-button"
    :class="[variant, size]"
    type="button"
    :disabled="disabled || loading"
    :aria-busy="loading"
    :aria-disabled="disabled || loading"
  >
    <LoaderCircle v-if="loading" class="spin" :size="15" aria-hidden="true" />
    <slot name="icon" v-else />
    <span class="button-label"><slot /></span>
  </button>
</template>

<script setup lang="ts">
import { LoaderCircle } from 'lucide-vue-next'

withDefaults(defineProps<{
  variant?: 'neutral' | 'primary' | 'success' | 'warning' | 'danger'
  size?: 'compact' | 'default'
  disabled?: boolean
  loading?: boolean
}>(), {
  variant: 'neutral',
  size: 'default',
  disabled: false,
  loading: false,
})
</script>

<style scoped>
.industrial-button{min-width:0;height:36px;display:inline-flex;align-items:center;justify-content:center;gap:7px;padding:0 13px;border:1px solid #315A83;border-radius:7px;color:#DDEBFF;background:linear-gradient(180deg,#122B49,#0A1D34);font:700 12px/1 'Microsoft YaHei UI','Segoe UI',sans-serif;white-space:nowrap;transition:filter 160ms ease,border-color 160ms ease,box-shadow 160ms ease,transform 160ms ease}.industrial-button.compact{height:32px;padding-inline:10px;font-size:11px}.industrial-button.primary{border-color:#2F80FF;background:linear-gradient(135deg,#176CD9,#0E4A98)}.industrial-button.success{border-color:#21C55D;background:linear-gradient(135deg,#0F7043,#0A4B32)}.industrial-button.warning{border-color:#D69D21;color:#FFF1C2;background:linear-gradient(135deg,#795719,#513A12)}.industrial-button.danger{border-color:#EF4444;color:#FFE8EC;background:linear-gradient(135deg,#B42534,#721B29)}.industrial-button:not(:disabled):hover{filter:brightness(1.18);border-color:#75B5FF;box-shadow:0 0 0 1px rgba(47,128,255,.22),0 5px 16px rgba(47,128,255,.22);transform:translateY(-1px)}.industrial-button.warning:not(:disabled):hover{border-color:#F6C343;box-shadow:0 0 0 1px rgba(246,195,67,.18),0 5px 16px rgba(246,195,67,.18)}.industrial-button.danger:not(:disabled):hover{border-color:#FF7B88;box-shadow:0 0 0 1px rgba(239,68,68,.2),0 5px 16px rgba(239,68,68,.22)}.industrial-button:focus-visible{outline:2px solid #9CCBFF;outline-offset:2px}.industrial-button:disabled{cursor:not-allowed;opacity:.42;filter:saturate(.55);box-shadow:none;transform:none}.button-label{min-width:0;overflow:hidden;text-overflow:ellipsis}.spin{animation:industrial-spin .85s linear infinite}@keyframes industrial-spin{to{transform:rotate(360deg)}}
</style>
