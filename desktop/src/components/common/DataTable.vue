<template>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th v-for="column in columns" :key="column.key">{{ column.label }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, index) in rows" :key="index">
          <td v-for="column in columns" :key="column.key">{{ value(row, column.key) }}</td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length" class="empty-cell">暂无数据</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  columns: Array<{ key: string; label: string }>
  rows: Array<Record<string, unknown>>
}>()

function value(row: Record<string, unknown>, key: string) {
  return String(row[key] ?? '')
}
</script>

<style scoped>
.table-wrap {
  overflow: auto;
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
th,
td {
  height: 34px;
  padding: 0 10px;
  border-bottom: 1px solid #173456;
  white-space: nowrap;
}
th {
  position: sticky;
  top: 0;
  background: #10243D;
  color: #C9D7EA;
  text-align: left;
}
td { color: #DDE8F9; }
tr:nth-child(even) td { background: rgba(255, 255, 255, .02); }
.empty-cell {
  text-align: center;
  color: var(--text-secondary);
  height: 68px;
}
</style>
