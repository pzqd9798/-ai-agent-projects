<template>
  <div class="layout-centered">
    <section class="panel panel-form panel-centered">
      <header class="panel-head">
        <div class="logo">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 2.5c-.7 0-1.4.2-2 .6L4.6 7C3.6 7.6 3 8.7 3 9.9v4.2c0 1.2.6 2.3 1.6 2.9l5.4 3.9c1.2.8 2.8.8 4 0l5.4-3.9c1-.7 1.6-1.7 1.6-2.9V9.9c0-1.2-.6-2.3-1.6-2.9L14 3.1a3.6 3.6 0 0 0-2-.6Z" />
          </svg>
        </div>
        <div>
          <h1>深度研究助手</h1>
          <p>结合多轮智能检索与总结，实时呈现洞见与引用。</p>
        </div>
      </header>

      <form class="form" @submit.prevent="handleSubmit">
        <label class="field">
          <span>研究主题</span>
          <textarea
            v-model="topicInput"
            placeholder="例如：探索多模态模型在 2025 年的关键突破"
            rows="4"
            required
          ></textarea>
        </label>

        <section class="options">
          <label class="field option">
            <span>搜索引擎</span>
            <select v-model="searchApiInput">
              <option value="">沿用后端配置</option>
              <option v-for="opt in searchOptions" :key="opt" :value="opt">{{ opt }}</option>
            </select>
          </label>
        </section>

        <div class="form-actions">
          <button class="submit" type="submit" :disabled="loading">
            <span class="submit-label">
              <svg v-if="loading" class="spinner" viewBox="0 0 24 24" aria-hidden="true">
                <circle cx="12" cy="12" r="9" stroke-width="3" />
              </svg>
              {{ loading ? "研究进行中..." : "开始研究" }}
            </span>
          </button>
          <button v-if="loading" type="button" class="secondary-btn" @click="cancelResearch">
            取消研究
          </button>
          <router-link to="/history" class="history-link">查看历史研究 →</router-link>
        </div>
      </form>

      <p v-if="error" class="error-chip">
        <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 3.2c-.3 0-.6.2-.8.5L3.4 15c-.4.7.1 1.6.8 1.6h11.6c.7 0 1.2-.9.8-1.6L10.8 3.7c-.2-.3-.5-.5-.8-.5Zm0 4.3c.4 0 .7.3.7.7v4c0 .4-.3.7-.7.7s-.7-.3-.7-.7V8.2c0-.4.3-.7.7-.7Zm0 6.6a1 1 0 1 1 0 2 1 1 0 0 1 0-2Z" /></svg>
        {{ error }}
      </p>
    </section>
  </div>
</template>

<script lang="ts" setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useResearchStore } from "../stores/research";
import { runResearchStream, type ResearchStreamEvent } from "../services/api";

const router = useRouter();
const store = useResearchStore();

const topicInput = ref("");
const searchApiInput = ref("");
const loading = ref(false);
const error = ref("");
const searchOptions = ["advanced", "duckduckgo", "tavily", "perplexity", "searxng"];

let currentController: AbortController | null = null;

const handleSubmit = async () => {
  if (!topicInput.value.trim()) {
    error.value = "请输入研究主题";
    return;
  }

  currentController = new AbortController();
  loading.value = true;
  error.value = "";
  store.resetState();
  store.isExpanded = true;
  store.topic = topicInput.value.trim();
  store.searchApi = searchApiInput.value;

  try {
    await runResearchStream(
      { topic: store.topic, search_api: store.searchApi || undefined },
      (event: ResearchStreamEvent) => {
        if (event.type === "todo_list") {
          const tasks = Array.isArray(event.tasks) ? event.tasks as any[] : [];
          store.todoTasks = tasks.map((item, idx) => ({
            id: item.id ?? idx + 1,
            title: item.title ?? `任务${idx + 1}`,
            intent: item.intent ?? "",
            query: item.query ?? store.topic,
            status: item.status ?? "pending",
            summary: "",
            sourcesSummary: "",
            sourceItems: [],
            notices: [],
            noteId: item.note_id ?? null,
            notePath: item.note_path ?? null,
            toolCalls: [],
          }));
          if (store.todoTasks.length) store.activeTaskId = store.todoTasks[0].id;
          store.addLog("已生成任务清单");
        } else if (event.type === "task_status") {
          const task = store.findTask(event.task_id);
          if (task) {
            task.status = typeof event.status === "string" ? event.status : task.status;
            if (event.summary) task.summary = event.summary as string;
            if (event.sources_summary) task.sourcesSummary = event.sources_summary as string;
            store.addLog(`任务状态: ${task.title} → ${task.status}`);
          }
        } else if (event.type === "final_report") {
          store.reportMarkdown = typeof event.report === "string" ? event.report : "";
          store.addLog("最终报告已生成");
        } else if (event.type === "status") {
          store.addLog(typeof event.message === "string" ? event.message : "状态更新");
        }
      },
      { signal: currentController.signal }
    );
    router.push("/research");
  } catch (err: any) {
    if (err.name === "AbortError") {
      store.addLog("研究已取消");
    } else {
      error.value = err.message || "研究请求失败";
    }
  } finally {
    loading.value = false;
    currentController = null;
  }
};

const cancelResearch = () => {
  currentController?.abort();
};
</script>

<style scoped>
.layout-centered { max-width: 600px; width: 100%; z-index: 1; }
.panel { position: relative; padding: 40px; border-radius: 20px; background: rgba(255,255,255,0.95); border: 1px solid rgba(148,163,184,0.18); box-shadow: 0 32px 64px rgba(15,23,42,0.15); }
.panel-centered { width: 100%; max-width: 600px; }
.panel-centered:hover { transform: scale(1.02); box-shadow: 0 40px 80px rgba(15,23,42,0.2); transition: transform 0.3s, box-shadow 0.3s; }
.panel-head { display: flex; align-items: center; gap: 16px; margin-bottom: 24px; }
.logo { width: 52px; height: 52px; display: grid; place-items: center; border-radius: 16px; background: linear-gradient(135deg, #2563eb, #7c3aed); box-shadow: 0 12px 28px rgba(59,130,246,0.4); }
.logo svg { width: 28px; height: 28px; fill: #f8fafc; }
h1 { margin: 0; font-size: 26px; }
.panel-head p { margin: 4px 0 0; color: #64748b; font-size: 13px; }
.form { display: flex; flex-direction: column; gap: 18px; }
.field { display: flex; flex-direction: column; gap: 10px; }
.field span { font-weight: 600; color: #475569; }
textarea, select { padding: 14px 16px; border-radius: 16px; border: 1px solid rgba(148,163,184,0.35); background: rgba(255,255,255,0.92); color: #1f2937; font-size: 14px; }
textarea:focus, select:focus { outline: none; border-color: rgba(37,99,235,0.65); box-shadow: 0 0 0 3px rgba(59,130,246,0.2); }
.options { display: flex; gap: 16px; flex-wrap: wrap; }
.option { flex: 1; min-width: 140px; }
.form-actions { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.submit { padding: 12px 24px; border-radius: 16px; border: none; background: linear-gradient(135deg, #2563eb, #7c3aed); color: #fff; font-size: 15px; font-weight: 600; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s, opacity 0.2s; display: inline-flex; align-items: center; gap: 10px; }
.submit:disabled { opacity: 0.7; cursor: not-allowed; }
.submit:not(:disabled):hover { transform: translateY(-2px); box-shadow: 0 12px 28px rgba(37,99,235,0.28); }
.submit-label { display: inline-flex; align-items: center; gap: 10px; }
.spinner { width: 18px; height: 18px; fill: none; stroke: rgba(255,255,255,0.85); stroke-linecap: round; animation: spin 1s linear infinite; }
.secondary-btn { padding: 10px 18px; border-radius: 14px; background: rgba(148,163,184,0.12); border: 1px solid rgba(148,163,184,0.28); color: #1f2937; font-size: 14px; cursor: pointer; }
.history-link { color: #2563eb; font-size: 13px; text-decoration: none; }
.error-chip { margin-top: 16px; display: inline-flex; align-items: center; gap: 8px; padding: 10px 14px; background: rgba(248,113,113,0.12); border: 1px solid rgba(248,113,113,0.35); border-radius: 14px; color: #b91c1c; font-size: 14px; }
.error-chip svg { width: 18px; height: 18px; fill: currentColor; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
