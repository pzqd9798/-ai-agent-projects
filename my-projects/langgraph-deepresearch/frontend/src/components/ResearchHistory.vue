<template>
  <div class="history-page">
    <div class="history-header">
      <router-link to="/" class="back-link">← 返回首页</router-link>
      <h1>历史研究</h1>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="error" class="error">{{ error }}</div>

    <div v-else-if="sessions.length === 0" class="empty">
      <p>暂无研究记录</p>
      <router-link to="/" class="start-btn">开始第一次研究</router-link>
    </div>

    <div v-else class="sessions-list">
      <div v-for="s in sessions" :key="s.id" class="session-card"
        @click="$router.push(`/research/${s.id}`)">
        <div class="card-left">
          <span class="status-dot" :class="s.status"></span>
          <div>
            <h3>{{ s.topic }}</h3>
            <p class="meta">
              {{ s.status }} · {{ s.todo_count }} 任务
              <span v-if="s.elapsed_ms"> · {{ (s.elapsed_ms / 1000).toFixed(1) }}s</span>
            </p>
          </div>
        </div>
        <div class="card-right">
          <span class="date">{{ formatDate(s.created_at) }}</span>
          <button class="delete-btn" @click.stop="deleteSession(s.id)">删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();
const sessions = ref<any[]>([]);
const loading = ref(true);
const error = ref("");

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const TOKEN = localStorage.getItem("access_token") || "";

const fetchSessions = async () => {
  try {
    loading.value = true;
    const resp = await fetch(`${API_BASE}/api/research/sessions`, {
      headers: { Authorization: `Bearer ${TOKEN}` },
    });
    if (!resp.ok) {
      if (resp.status === 401) {
        error.value = "请先登录";
        return;
      }
      throw new Error(`HTTP ${resp.status}`);
    }
    const data = await resp.json();
    sessions.value = data.sessions || [];
  } catch (e: any) {
    error.value = e.message || "加载失败";
  } finally {
    loading.value = false;
  }
};

const deleteSession = async (id: number) => {
  try {
    await fetch(`${API_BASE}/api/research/sessions/${id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${TOKEN}` },
    });
    sessions.value = sessions.value.filter((s) => s.id !== id);
  } catch (e: any) {
    error.value = e.message;
  }
};

const formatDate = (d: string | null) => {
  if (!d) return "";
  return new Date(d).toLocaleDateString("zh-CN");
};

onMounted(fetchSessions);
</script>

<style scoped>
.history-page { max-width: 800px; margin: 0 auto; padding: 40px 20px; z-index: 1; position: relative; }
.history-header { display: flex; align-items: center; gap: 20px; margin-bottom: 32px; }
.back-link { color: #2563eb; text-decoration: none; font-size: 14px; }
h1 { margin: 0; font-size: 28px; }
.loading, .error, .empty { text-align: center; padding: 60px 0; color: #64748b; }
.start-btn { display: inline-block; margin-top: 12px; padding: 10px 20px; background: linear-gradient(135deg, #2563eb, #7c3aed); color: #fff; border-radius: 12px; text-decoration: none; font-weight: 600; }
.sessions-list { display: flex; flex-direction: column; gap: 12px; }
.session-card { background: rgba(255,255,255,0.94); border: 1px solid rgba(148,163,184,0.2); border-radius: 16px; padding: 20px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; transition: box-shadow 0.2s, border-color 0.2s; }
.session-card:hover { box-shadow: 0 8px 24px rgba(15,23,42,0.1); border-color: rgba(59,130,246,0.3); }
.card-left { display: flex; align-items: center; gap: 14px; }
.status-dot { width: 10px; height: 10px; border-radius: 999px; }
.status-dot.completed { background: #22c55e; }
.status-dot.running { background: #3b82f6; animation: pulse 1.5s infinite; }
.status-dot.failed { background: #ef4444; }
.status-dot.pending { background: #94a3b8; }
h3 { margin: 0; font-size: 16px; }
.meta { margin: 4px 0 0; font-size: 13px; color: #64748b; }
.card-right { display: flex; align-items: center; gap: 12px; }
.date { font-size: 13px; color: #94a3b8; }
.delete-btn { padding: 6px 12px; border-radius: 8px; border: 1px solid rgba(248,113,113,0.4); background: rgba(248,113,113,0.08); color: #b91c1c; font-size: 12px; cursor: pointer; }
.delete-btn:hover { background: rgba(248,113,113,0.2); }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
</style>
