<template>
  <span :class="['page-data-state', state, { idle: !visible }]" role="status" :data-state="visible ? state : 'idle'" :aria-hidden="!visible">
    <template v-if="visible">
      <LoaderCircle v-if="state === 'loading'" :size="13" class="spin" />
      <ShieldX v-else-if="state === 'permission-denied'" :size="13" />
      <TriangleAlert v-else-if="state === 'error'" :size="13" />
      <ClockAlert v-else-if="state === 'stale'" :size="13" />
      <Inbox v-else :size="13" />
      {{ label }}
    </template>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ClockAlert, Inbox, LoaderCircle, ShieldX, TriangleAlert } from 'lucide-vue-next'

const props = withDefaults(defineProps<{
  loading?: boolean
  error?: string
  empty?: boolean
  stale?: boolean
  staleLabel?: string
}>(), {
  loading: false,
  error: '',
  empty: false,
  stale: false,
  staleLabel: '数据已陈旧或离线，实时值不参与判断',
})

const permissionDenied = computed(() => /(^|\D)(401|403)(\D|$)|forbidden|permission|权限不足|无权/i.test(props.error))
const state = computed<'loading' | 'permission-denied' | 'error' | 'stale' | 'empty'>(() => {
  if (props.loading) return 'loading'
  if (permissionDenied.value) return 'permission-denied'
  if (props.error) return 'error'
  if (props.stale) return 'stale'
  return 'empty'
})
const visible = computed(() => props.loading || Boolean(props.error) || props.stale || props.empty)
const label = computed(() => {
  if (state.value === 'loading') return '正在加载'
  if (state.value === 'permission-denied') return '权限不足，操作未执行'
  if (state.value === 'error') return `加载失败：${props.error}`
  if (state.value === 'stale') return props.staleLabel
  return '暂无数据'
})
</script>

<style scoped>
.page-data-state{width:min(360px,30vw);height:28px;max-width:460px;display:inline-flex;align-items:center;gap:5px;padding:0 9px;border:1px solid rgba(126,151,184,.5);border-radius:5px;color:#AFC2DA;background:rgba(15,36,61,.92);font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.page-data-state.idle{visibility:hidden;pointer-events:none}.page-data-state.loading{color:#8FC2FF;border-color:rgba(47,128,255,.5)}.page-data-state.stale,.page-data-state.empty{color:#F6C343;border-color:rgba(246,195,67,.5);background:rgba(74,53,18,.92)}.page-data-state.error,.page-data-state.permission-denied{color:#FF9AA7;border-color:rgba(239,68,68,.6);background:rgba(70,19,29,.94)}.spin{animation:state-spin 1s linear infinite}@keyframes state-spin{to{transform:rotate(360deg)}}
</style>
