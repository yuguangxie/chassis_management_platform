<template><span :class="['pill', status]"><i></i>{{ label }}</span></template>
<script setup lang="ts">
defineProps<{ status: 'normal'|'warning'|'fault'|'unknown'|'pass'|'fail'; label: string }>()
</script>
<style scoped>.pill{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--border-subtle);padding:3px 9px;border-radius:999px;font-weight:700;font-size:12px}.pill i{width:8px;height:8px;border-radius:50%;background:currentColor}.normal,.pass{color:var(--success)}.warning{color:var(--warning)}.fault,.fail{color:var(--danger)}.unknown{color:#789}</style>
