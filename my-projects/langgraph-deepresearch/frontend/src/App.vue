<template>
  <main class="app-shell" :class="{ expanded: store.isExpanded }">
    <div class="aurora" aria-hidden="true">
      <span></span>
      <span></span>
      <span></span>
    </div>
    <router-view />
  </main>
</template>

<script lang="ts" setup>
import { useResearchStore } from "./stores/research";

const store = useResearchStore();
</script>

<style scoped>
.app-shell {
  position: relative;
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background: radial-gradient(circle at 20% 20%, #f8fafc, #dbeafe 60%);
  color: #1f2937;
  overflow: hidden;
  box-sizing: border-box;
  transition: padding 0.4s ease;
  padding: 72px 24px;
}

.app-shell.expanded {
  padding: 0;
  align-items: stretch;
}

.aurora {
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.55;
}

.aurora span {
  position: absolute;
  width: 45vw;
  height: 45vw;
  max-width: 520px;
  max-height: 520px;
  background: radial-gradient(circle, rgba(148, 197, 255, 0.35), transparent 60%);
  filter: blur(90px);
  animation: float 26s infinite linear;
}

.aurora span:nth-child(1) { top: -20%; left: -18%; animation-delay: 0s; }
.aurora span:nth-child(2) { bottom: -25%; right: -20%; background: radial-gradient(circle, rgba(166, 139, 255, 0.28), transparent 60%); animation-delay: -9s; }
.aurora span:nth-child(3) { top: 35%; left: 45%; background: radial-gradient(circle, rgba(164, 219, 216, 0.26), transparent 60%); animation-delay: -16s; }

@keyframes float {
  0% { transform: translate3d(0, 0, 0) rotate(0deg); }
  50% { transform: translate3d(10%, 6%, 0) rotate(3deg); }
  100% { transform: translate3d(0, 0, 0) rotate(0deg); }
}
</style>
