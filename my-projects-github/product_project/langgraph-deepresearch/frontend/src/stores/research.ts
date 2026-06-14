import { defineStore } from "pinia";
import { ref, computed } from "vue";

export interface TodoTask {
  id: number;
  title: string;
  intent: string;
  query: string;
  status: string; // pending | in_progress | completed | skipped
  summary: string;
  sourcesSummary: string;
  sourceItems: SourceItem[];
  notices: string[];
  noteId: string | null;
  notePath: string | null;
  toolCalls: ToolCallEntry[];
}

export interface SourceItem {
  title: string;
  url: string;
  snippet: string;
  raw: string;
}

export interface ToolCallEntry {
  eventId: number;
  agent: string;
  tool: string;
  parameters: Record<string, unknown>;
  result: string;
  noteId: string | null;
  notePath: string | null;
  timestamp: number;
}

export const useResearchStore = defineStore("research", () => {
  // State
  const isExpanded = ref(false);
  const loading = ref(false);
  const error = ref("");
  const progressLogs = ref<string[]>([]);
  const logsCollapsed = ref(false);

  const todoTasks = ref<TodoTask[]>([]);
  const activeTaskId = ref<number | null>(null);
  const reportMarkdown = ref("");

  const topic = ref("");
  const searchApi = ref("");
  const sessionId = ref<number | null>(null);

  // Computed
  const totalTasks = computed(() => todoTasks.value.length);
  const completedTasks = computed(() =>
    todoTasks.value.filter((t) => t.status === "completed").length
  );
  const currentTask = computed(() => {
    if (activeTaskId.value !== null) {
      return todoTasks.value.find((t) => t.id === activeTaskId.value) ?? null;
    }
    return todoTasks.value[0] ?? null;
  });

  // Actions
  function resetState() {
    todoTasks.value = [];
    activeTaskId.value = null;
    reportMarkdown.value = "";
    progressLogs.value = [];
    error.value = "";
    logsCollapsed.value = false;
  }

  function findTask(taskId: unknown): TodoTask | undefined {
    const numeric =
      typeof taskId === "number"
        ? taskId
        : typeof taskId === "string"
        ? Number(taskId)
        : NaN;
    if (Number.isNaN(numeric)) return undefined;
    return todoTasks.value.find((t) => t.id === numeric);
  }

  function addLog(message: string) {
    progressLogs.value.push(message);
  }

  return {
    isExpanded,
    loading,
    error,
    progressLogs,
    logsCollapsed,
    todoTasks,
    activeTaskId,
    reportMarkdown,
    topic,
    searchApi,
    sessionId,
    totalTasks,
    completedTasks,
    currentTask,
    resetState,
    findTask,
    addLog,
  };
});
