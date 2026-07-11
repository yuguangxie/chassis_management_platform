<template>
  <div class="window-chrome">
    <div class="drag-title">
      <span class="mark"></span>
      <span>低速无人车线控底盘生产下线管理平台</span>
    </div>
    <div class="window-actions">
      <button aria-label="最小化" type="button" @click="controls.minimize">-</button>
      <button aria-label="最大化" type="button" @click="controls.maximize">□</button>
      <button class="close" aria-label="关闭" type="button" @click="controls.close">×</button>
    </div>
  </div>
</template>

<script setup lang="ts">
const controls = window.windowControls ?? {
  minimize: () => undefined,
  maximize: () => undefined,
  close: () => undefined,
}
</script>

<style scoped>
.window-chrome {
  height: var(--chrome-height);
  background: linear-gradient(90deg, #06101E, #08172A 48%, #06101E);
  border-bottom: 1px solid #122B49;
  display: flex;
  align-items: center;
  justify-content: space-between;
  -webkit-app-region: drag;
  user-select: none;
}

.drag-title {
  display: flex;
  align-items: center;
  gap: 9px;
  padding-left: 16px;
  color: #AFC2DD;
  font-size: 12px;
  letter-spacing: 0;
}

.mark {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--primary);
  box-shadow: 0 0 12px rgba(47, 128, 255, .8);
}

.window-actions {
  height: 100%;
  display: flex;
  -webkit-app-region: no-drag;
}

.window-actions button {
  width: 44px;
  height: 100%;
  border: 0;
  background: transparent;
  color: #B7C9E5;
  font-size: 14px;
}

.window-actions button:hover { background: #10243D; }

.window-actions .close:hover {
  background: #A91E32;
  color: white;
}
</style>
