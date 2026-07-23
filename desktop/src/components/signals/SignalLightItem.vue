<template>
  <div class="signal-light" :class="[`tone-${tone}`, binaryState]" :data-state="binaryState" :data-quality="quality">
    <span class="label">{{ label }}</span>
    <i class="lamp" aria-hidden="true"><slot /></i>
    <strong>{{ binaryStateLabel(binaryState, quality) }}</strong>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { binaryStateLabel, normalizeBinaryState } from '../../ui/uiStatusLabels'

const props = defineProps<{
  label: string
  value: string | number | boolean | null | undefined
  quality: string
  tone: 'yellow' | 'red' | 'white'
}>()

const binaryState = computed(() => normalizeBinaryState(props.value, props.quality))
</script>

<style scoped>
.signal-light{--lamp-color:#94A3B8;min-width:0;display:grid;place-items:center;gap:9px;border-right:1px solid rgba(30,58,95,.78);border-top:1px solid transparent;border-bottom:1px solid transparent;color:#93A4BA;background:rgba(8,26,45,.46);transition:border-color 160ms ease,background 160ms ease,box-shadow 160ms ease,color 160ms ease}.signal-light:first-child{border-left:1px solid transparent;border-radius:7px 0 0 7px}.signal-light:last-child{border-right:1px solid transparent;border-radius:0 7px 7px 0}.lamp{height:36px;display:grid;place-items:center;color:#94A3B8;font-style:normal;transition:filter 160ms ease}.signal-light strong{font-size:13px}.signal-light.on.tone-yellow{--lamp-color:#F6C343}.signal-light.on.tone-red{--lamp-color:#EF4444}.signal-light.on.tone-white{--lamp-color:#F8FAFC}.signal-light.on{color:var(--lamp-color);border-color:color-mix(in srgb,var(--lamp-color) 60%,transparent);background:color-mix(in srgb,var(--lamp-color) 10%,rgba(8,26,45,.76));box-shadow:inset 0 0 18px color-mix(in srgb,var(--lamp-color) 12%,transparent)}.signal-light.on .lamp{color:var(--lamp-color);filter:drop-shadow(0 0 7px color-mix(in srgb,var(--lamp-color) 75%,transparent))}.signal-light.unknown{color:#F6C343;background:rgba(74,53,18,.25)}.signal-light.unknown .lamp{color:#788A9F;filter:none}.signal-light.off .lamp{color:#94A3B8;filter:none}
</style>
