<template>
  <button
    class="industrial-action"
    :class="variant"
    type="button"
    :disabled="disabled || loading"
    :aria-busy="loading"
    :aria-disabled="disabled || loading"
    :title="subtitle ? `${title}：${subtitle}` : title"
  >
    <span class="icon-block" aria-hidden="true">
      <LoaderCircle v-if="loading" class="spin" :size="24" />
      <slot name="icon" v-else />
    </span>
    <span class="action-copy">
      <strong>{{ title }}</strong>
      <small v-if="subtitle">{{ subtitle }}</small>
    </span>
  </button>
</template>

<script setup lang="ts">
import { LoaderCircle } from 'lucide-vue-next'

withDefaults(defineProps<{
  title: string
  subtitle?: string
  variant?: 'neutral' | 'primary' | 'success' | 'warning' | 'danger'
  disabled?: boolean
  loading?: boolean
}>(), {
  subtitle: '',
  variant: 'primary',
  disabled: false,
  loading: false,
})
</script>

<style scoped>
.industrial-action{container-type:inline-size;min-width:0;height:70px;display:flex;align-items:center;justify-content:center;gap:12px;padding:0 14px;border:1px solid #2F80FF;border-radius:7px;color:#EAF2FF;background:linear-gradient(135deg,rgba(23,108,217,.78),rgba(14,74,152,.68));font-family:'Microsoft YaHei UI','Segoe UI',sans-serif;text-align:left;transition:filter 160ms ease,border-color 160ms ease,box-shadow 160ms ease,transform 160ms ease}.icon-block{width:42px;height:42px;flex:0 0 auto;display:grid;place-items:center;border-radius:7px;color:#BBD8FF;background:rgba(47,128,255,.23);box-shadow:inset 0 0 0 1px rgba(137,192,255,.09)}.action-copy{min-width:0;display:grid;gap:4px}.action-copy strong,.action-copy small{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.action-copy strong{font-size:14px;line-height:17px}.action-copy small{color:#9FC6F6;font-size:9px;line-height:12px}.industrial-action.neutral{border-color:#315A83;background:linear-gradient(135deg,#122B49,#0A1D34)}.industrial-action.success{border-color:#21C55D;background:linear-gradient(135deg,rgba(15,112,67,.82),rgba(10,75,50,.72))}.industrial-action.warning{border-color:#D69D21;color:#FFF1C2;background:linear-gradient(135deg,rgba(121,87,25,.92),rgba(81,58,18,.88))}.industrial-action.danger{border-color:#EF4444;color:#FFE8EC;background:linear-gradient(135deg,#B42534,#721B29)}.industrial-action.danger .icon-block{color:#FFD2D8;background:rgba(239,68,68,.22)}.industrial-action:not(:disabled):hover{filter:brightness(1.2);border-color:#87C0FF;box-shadow:0 0 0 1px rgba(47,128,255,.2),0 7px 20px rgba(47,128,255,.24);transform:translateY(-1px)}.industrial-action.warning:not(:disabled):hover{border-color:#F6C343;box-shadow:0 0 0 1px rgba(246,195,67,.18),0 7px 20px rgba(246,195,67,.2)}.industrial-action.danger:not(:disabled):hover{border-color:#FF7B88;box-shadow:0 0 0 1px rgba(239,68,68,.2),0 7px 20px rgba(239,68,68,.24)}.industrial-action:focus-visible{outline:2px solid #9CCBFF;outline-offset:2px}.industrial-action:disabled{cursor:not-allowed;opacity:.42;filter:saturate(.55);box-shadow:none;transform:none}.spin{animation:industrial-spin .85s linear infinite}@keyframes industrial-spin{to{transform:rotate(360deg)}}
@container (max-width:165px){.icon-block{display:none}.action-copy strong{font-size:12px}.action-copy small{display:none}}
</style>
