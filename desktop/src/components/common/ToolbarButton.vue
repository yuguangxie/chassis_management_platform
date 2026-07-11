<template>
  <button :class="['btn', variant]">
    <slot />
  </button>
</template>

<script setup lang="ts">
defineProps({
  variant: { type: String, default: "" },
})
</script>
