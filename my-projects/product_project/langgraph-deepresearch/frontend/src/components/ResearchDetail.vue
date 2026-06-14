<template>
  <div class="layout-fullscreen">
    <aside class="sidebar">
      <div class="sidebar-header">
        <button class="back-btn" @click="goBack" :disabled="store.loading">
          <svg viewBox="0 0 24 24" width="20" height="20"><path d="M19 12H5M12 19l-7-7 7-7" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>
          返回
        </button>
        <h2>🔍 深度研究助手</h2>
      </div>

      <div class="research-info">
        <div class="info-item">
          <label>研究主题</label>
          <p class="topic-display">{{ store.topic }}</p>
        </div>
        <div class="info-item" v-if="store.searchApi">
          <label>搜索引擎</label>
          <p>{{ store.searchApi }}</p>
        </div>
        <div class="info-item" v-if="store.totalTasks > 0">
          <label>研究进度</label>
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: `${progressPct}%` }"></div>
          </div>
          <p class="progress-text">{{ store.completedTasks }} / {{ store.totalTasks }} 任务完成</p>
        </div>
      </div>

      <div class="sidebar-actions">
        <router-link to="/history" class="new-research-btn secondary">📋 查看历史</router-link>
        <button class="new-research-btn" @click="startNew">✨ 开始新研究</button>
      </div>
    </aside>

    <section class="panel-result">
      <!-- Timeline -->
      <div v-if="store.progressLogs.length" class="timeline-wrapper" :class="{ collapsed: store.logsCollapsed }">
        <div class="status-bar">
          <span class="status-chip" :class="{ active: store.loading }">
            <span class="dot"></span>
            {{ store.loading ? "研究进行中" : "研究完成" }}
          </span>
          <button class="secondary-btn sm" @click="store.logsCollapsed = !store.logsCollapsed">
            {{ store.logsCollapsed ? "展开流程" : "收起流程" }}
          </button>
        </div>
        <ul class="timeline" v-show="!store.logsCollapsed">
          <li v-for="(log, idx) in store.progressLogs" :key="idx">
            <span class="timeline-node"></span>
            <p>{{ log }}</p>
          </li>
        </ul>
      </div>

      <!-- Task List -->
      <div class="tasks-section" v-if="store.todoTasks.length">
        <aside class="tasks-list">
          <h3>任务清单</h3>
          <ul>
            <li v-for="task in store.todoTasks" :key="task.id"
              :class="['task-item', { active: task.id === store.activeTaskId, completed: task.status === 'completed' }]">
              <button type="button" class="task-button" @click="store.activeTaskId = task.id">
                <span class="task-title">{{ task.title }}</span>
                <span class="task-status" :class="task.status">{{ formatStatus(task.status) }}</span>
              </button>
            </li>
          </ul>
        </aside>

        <article class="task-detail" v-if="store.currentTask">
          <h3>{{ store.currentTask.title }}</h3>
          <p class="muted">{{ store.currentTask.intent }}</p>
          <p class="task-label">查询：{{ store.currentTask.query }}</p>

          <section v-if="store.currentTask.summary" class="summary-block">
            <h3>任务总结</h3>
            <pre class="block-pre">{{ store.currentTask.summary }}</pre>
          </section>
        </article>
      </div>

      <!-- Report -->
      <div v-if="store.reportMarkdown" class="report-block">
        <h3>最终报告</h3>
        <pre class="block-pre">{{ store.reportMarkdown }}</pre>
      </div>
    </section>
  </div>
</template>

<script lang="ts" setup>
import { computed } from "vue";
import { useRouter } from "vue-router";
import { useResearchStore } from "../stores/research";

const router = useRouter();
const store = useResearchStore();

const progressPct = computed(() =>
  store.totalTasks > 0 ? (store.completedTasks / store.totalTasks) * 100 : 0
);

const formatStatus = (s: string) => {
  const map: Record<string, string> = {
    pending: "待执行", in_progress: "进行中", completed: "已完成", skipped: "已跳过",
  };
  return map[s] ?? s;
};

const goBack = () => {
  if (!store.loading) router.push("/");
};

const startNew = () => router.push("/");
</script>

<style scoped>
.layout-fullscreen { width: 100%; height: 100vh; display: flex; gap: 0; z-index: 1; }
.sidebar { width: 340px; min-width: 340px; height: 100vh; background: rgba(255,255,255,0.98); border-right: 1px solid rgba(148,163,184,0.2); padding: 32px 24px; display: flex; flex-direction: column; gap: 24px; overflow-y: auto; }
.sidebar-header { display: flex; flex-direction: column; gap: 12px; }
.sidebar-header h2 { font-size: 22px; font-weight: 700; margin: 0; }
.back-btn { display: flex; align-items: center; gap: 8px; padding: 8px 14px; background: transparent; border: 1px solid rgba(148,163,184,0.3); border-radius: 10px; color: #64748b; cursor: pointer; width: fit-content; }
.back-btn:hover:not(:disabled) { background: rgba(59,130,246,0.1); border-color: #3b82f6; color: #3b82f6; }
.research-info { flex: 1; display: flex; flex-direction: column; gap: 16px; }
.info-item { display: flex; flex-direction: column; gap: 6px; }
.info-item label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: #64748b; }
.topic-display { font-size: 15px; font-weight: 600; padding: 10px; background: rgba(59,130,246,0.05); border-radius: 8px; border-left: 3px solid #3b82f6; margin: 0; }
.progress-bar { width: 100%; height: 8px; background: rgba(148,163,184,0.2); border-radius: 4px; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #8b5cf6); border-radius: 4px; transition: width 0.5s; }
.progress-text { font-size: 13px; color: #64748b; margin: 0; }
.sidebar-actions { display: flex; flex-direction: column; gap: 8px; padding-top: 16px; border-top: 1px solid rgba(148,163,184,0.2); }
.new-research-btn { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 12px 16px; background: linear-gradient(135deg, #3b82f6, #8b5cf6); border: none; border-radius: 10px; color: #fff; font-size: 14px; font-weight: 600; cursor: pointer; text-decoration: none; }
.new-research-btn.secondary { background: rgba(148,163,184,0.12); color: #1f2937; }
.panel-result { flex: 1; height: 100vh; overflow-y: auto; padding: 24px; display: flex; flex-direction: column; gap: 18px; }
.status-bar { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.status-chip { display: inline-flex; align-items: center; gap: 8px; background: rgba(191,219,254,0.28); padding: 8px 14px; border-radius: 999px; font-size: 13px; border: 1px solid rgba(59,130,246,0.35); }
.status-chip.active { background: rgba(129,140,248,0.2); }
.dot { width: 8px; height: 8px; border-radius: 999px; background: #2563eb; box-shadow: 0 0 12px rgba(37,99,235,0.45); animation: pulse 1.8s infinite; }
.secondary-btn { padding: 8px 14px; border-radius: 10px; background: rgba(148,163,184,0.12); border: 1px solid rgba(148,163,184,0.28); color: #1f2937; font-size: 13px; cursor: pointer; }
.timeline-wrapper { max-height: 180px; overflow-y: auto; }
.timeline-wrapper.collapsed { max-height: auto; }
.timeline { list-style: none; padding: 0 0 0 12px; margin: 12px 0 0; display: flex; flex-direction: column; gap: 10px; position: relative; }
.timeline::before { content: ""; position: absolute; top: 8px; bottom: 8px; left: 0; width: 2px; background: linear-gradient(180deg, rgba(59,130,246,0.35), rgba(129,140,248,0.15)); }
.timeline li { position: relative; padding-left: 24px; font-size: 13px; }
.timeline-node { position: absolute; left: -12px; top: 4px; width: 10px; height: 10px; border-radius: 999px; background: linear-gradient(135deg, #38bdf8, #7c3aed); }
.tasks-section { display: grid; grid-template-columns: 250px 1fr; gap: 20px; }
.tasks-list { background: rgba(255,255,255,0.92); border: 1px solid rgba(148,163,184,0.26); border-radius: 18px; padding: 18px; }
.tasks-list h3 { margin: 0 0 12px; font-size: 15px; }
.tasks-list ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.task-item { border-radius: 12px; border: 1px solid transparent; padding: 8px 12px; transition: background 0.2s; }
.task-item.active { border-color: rgba(129,140,248,0.5); background: rgba(224,231,255,0.5); }
.task-item.completed { border-color: rgba(34,197,94,0.35); background: rgba(191,219,254,0.28); }
.task-button { width: 100%; display: flex; justify-content: space-between; align-items: center; background: none; border: none; cursor: pointer; text-align: left; padding: 4px 0; }
.task-title { font-weight: 600; font-size: 13px; }
.task-status { font-size: 11px; padding: 2px 8px; border-radius: 999px; }
.task-status.pending { background: rgba(148,163,184,0.18); color: #475569; }
.task-status.in_progress { background: rgba(129,140,248,0.24); color: #312e81; }
.task-status.completed { background: rgba(34,197,94,0.2); color: #15803d; }
.task-detail { background: rgba(255,255,255,0.94); border: 1px solid rgba(148,163,184,0.26); border-radius: 18px; padding: 22px; }
.task-label { display: inline-block; padding: 4px 10px; border-radius: 999px; background: rgba(191,219,254,0.32); font-size: 12px; }
.summary-block, .report-block { background: rgba(255,255,255,0.94); border: 1px solid rgba(148,163,184,0.26); border-radius: 18px; padding: 18px; }
.block-pre { font-family: monospace; font-size: 13px; line-height: 1.7; white-space: pre-wrap; word-break: break-word; color: #1f2937; background: rgba(248,250,252,0.9); padding: 16px; border-radius: 14px; border: 1px solid rgba(148,163,184,0.35); overflow: auto; max-height: 400px; }
.muted { color: #64748b; font-size: 13px; }
@keyframes pulse { 0%,100% { transform: scale(1); opacity: 1; } 50% { transform: scale(1.3); opacity: 0.5; } }
</style>
