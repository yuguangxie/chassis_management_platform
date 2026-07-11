<template><div ref="el" class="chart"></div></template>
<script setup lang="ts">
import * as echarts from 'echarts'
import type { PropType } from 'vue'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({ option: { type: Object as PropType<Record<string, unknown>>, required: true } })
const el = ref<HTMLElement>()
let chart: echarts.ECharts | undefined
let observer: ResizeObserver | undefined
function ensureChart() {
  if (!el.value || el.value.clientWidth <= 0 || el.value.clientHeight <= 0) return
  if (!chart) chart = echarts.init(el.value, 'dark')
  chart.setOption(props.option, true)
  chart.resize()
}
onMounted(async () => { await nextTick(); observer = new ResizeObserver(ensureChart); if (el.value) observer.observe(el.value); ensureChart() })
onBeforeUnmount(() => { observer?.disconnect(); chart?.dispose(); chart = undefined })
watch(() => props.option, () => { void nextTick(ensureChart) }, { deep: true })
</script>
<style scoped>.chart{height:220px;width:100%;min-height:0}</style>
