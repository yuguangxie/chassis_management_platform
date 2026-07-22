<template><div ref="el" class="chart" :style="{ height }"></div></template>
<script setup lang="ts">
import * as echarts from 'echarts'
import type { PropType } from 'vue'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  option: { type: Object as PropType<Record<string, unknown>>, required: true },
  height: { type: String, default: '220px' },
})
const el = ref<HTMLElement>()
let chart: echarts.ECharts | undefined
let observer: ResizeObserver | undefined
let resizeFrame: number | undefined
function ensureChart() {
  if (!el.value || el.value.clientWidth <= 0 || el.value.clientHeight <= 0) return
  if (!chart) chart = echarts.init(el.value, 'dark')
  chart.setOption(props.option, true)
  chart.resize()
}
function scheduleResize() {
  if (resizeFrame) window.cancelAnimationFrame(resizeFrame)
  resizeFrame = window.requestAnimationFrame(() => {
    resizeFrame = undefined
    ensureChart()
  })
}
onMounted(async () => {
  await nextTick()
  observer = new ResizeObserver(scheduleResize)
  if (el.value) observer.observe(el.value)
  window.addEventListener('resize', scheduleResize)
  scheduleResize()
})
onBeforeUnmount(() => {
  observer?.disconnect()
  window.removeEventListener('resize', scheduleResize)
  if (resizeFrame) window.cancelAnimationFrame(resizeFrame)
  chart?.dispose()
  chart = undefined
})
watch(() => props.option, () => { void nextTick(scheduleResize) }, { deep: true })
</script>
<style scoped>.chart{width:100%;min-height:0}</style>
