<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { getEvals } from "./api/evals";
import { getSystemStatus } from "./api/system";
import {
  confirmTask,
  createAgentTask,
  getTask,
  listTasks,
  rejectTask
} from "./api/tasks";
import { listTriggers, tickTriggers } from "./api/triggers";
import type {
  DemoTaskResponse,
  DynamicState,
  EvalBundle,
  PlanStep,
  SystemStatus,
  Task,
  Trigger
} from "./types";

type Preset = {
  id: string;
  label: string;
  text: string;
};

const presets: Preset[] = [
  {
    id: "morning",
    label: "早高峰通勤",
    text: "明早 8:30 公司开会，帮我安排好出门并提醒我。"
  },
  {
    id: "smart-home",
    label: "智能家居安全",
    text: "把客厅灯关掉"
  },
  {
    id: "vehicle",
    label: "车辆安全操作",
    text: "解锁我的车"
  }
];

const statusLabels: Record<string, string> = {
  CREATED: "已创建",
  PLANNED: "已规划",
  WAITING_CONFIRMATION: "等待确认",
  EXECUTING: "执行中",
  COMPLETED: "已完成",
  FAILED: "执行失败",
  CANCELLED: "已取消",
  PENDING: "待处理",
  RUNNING: "运行中",
  SUCCESS: "成功",
  ACTIVE: "生效中",
  FIRED: "已触发",
  EXPIRED: "已过期"
};

const confirmationLabels: Record<string, string> = {
  NOT_REQUIRED: "无需确认",
  PENDING: "待确认",
  CONFIRMED: "已确认",
  REJECTED: "已拒绝"
};

const riskLabels: Record<string, string> = {
  LOW: "低风险",
  MEDIUM: "中风险",
  HIGH: "高风险"
};

const toolLabels: Record<string, string> = {
  calendar_tool: "日程查询",
  weather_tool: "天气查询",
  navigation_tool: "路线规划",
  notification_tool: "通知提醒",
  smart_home_tool: "智能家居",
  vehicle_tool: "车辆控制"
};

const providerLabels: Record<string, string> = {
  calendar: "日程",
  weather: "天气",
  navigation: "路线",
  notification: "通知",
  smart_home: "智能家居",
  vehicle: "车辆",
  google_calendar: "Google Calendar",
  open_meteo: "Open-Meteo",
  amap: "Amap",
  feishu: "Feishu"
};

const providerValueLabels: Record<string, string> = {
  Mock: "安全演示能力",
  "Open-Meteo Real Active": "Open-Meteo 真实服务启用",
  "Amap Real Active": "Amap 真实服务启用",
  verified: "真实服务已验证",
  engineering_ready_real_pending: "工程就绪，真实发送待验收"
};

const selectedPreset = ref<Preset>(presets[0]);
const userInput = ref(presets[0].text);
const tasks = ref<Task[]>([]);
const triggers = ref<Trigger[]>([]);
const selectedTask = ref<Task | null>(null);
const currentResponse = ref<DemoTaskResponse | null>(null);
const systemStatus = ref<SystemStatus | null>(null);
const evals = ref<EvalBundle | null>(null);
const loading = ref(false);
const initialLoading = ref(true);
const error = ref<string | null>(null);
const info = ref<string | null>(null);

const currentTask = computed(() => selectedTask.value ?? currentResponse.value?.task ?? currentResponse.value?.notification_task ?? null);
const confirmationTask = computed(() => currentResponse.value?.notification_task ?? currentTask.value);
const timelineState = computed(() =>
  currentResponse.value?.task?.id === currentTask.value?.id
    ? currentResponse.value?.dynamic_state ?? null
    : null
);
const pendingConfirmation = computed(
  () =>
    confirmationTask.value?.requires_confirmation === true &&
    confirmationTask.value.confirmation_status === "PENDING" &&
    confirmationTask.value.status === "WAITING_CONFIRMATION"
);

function selectPreset(preset: Preset) {
  selectedPreset.value = preset;
  userInput.value = preset.text;
  info.value = null;
}

async function refreshAll() {
  error.value = null;
  try {
    const [system, taskList, triggerList, evalBundle] = await Promise.all([
      getSystemStatus(),
      listTasks(),
      listTriggers(),
      getEvals()
    ]);
    systemStatus.value = system;
    tasks.value = taskList;
    triggers.value = triggerList;
    evals.value = evalBundle;
  } finally {
    initialLoading.value = false;
  }
}

async function runAgent() {
  loading.value = true;
  error.value = null;
  info.value = null;
  selectedTask.value = null;
  currentResponse.value = null;
  try {
    currentResponse.value = await createAgentTask(userInput.value);
    await refreshAll();
    info.value = "FlowMate 已完成理解、规划和执行。";
  } catch (caught) {
    error.value = safeMessage(caught);
  } finally {
    loading.value = false;
  }
}

async function chooseTask(taskId: string) {
  loading.value = true;
  error.value = null;
  try {
    selectedTask.value = await getTask(taskId);
    currentResponse.value = null;
  } catch (caught) {
    error.value = safeMessage(caught);
  } finally {
    loading.value = false;
  }
}

async function onConfirm() {
  if (!confirmationTask.value) return;
  loading.value = true;
  error.value = null;
  try {
    selectedTask.value = await confirmTask(confirmationTask.value.id);
    currentResponse.value = null;
    await refreshAll();
    info.value = "已确认执行，后端已完成处理。";
  } catch (caught) {
    error.value = safeMessage(caught);
  } finally {
    loading.value = false;
  }
}

async function onReject() {
  if (!confirmationTask.value) return;
  loading.value = true;
  error.value = null;
  try {
    selectedTask.value = await rejectTask(confirmationTask.value.id);
    currentResponse.value = null;
    await refreshAll();
    info.value = "已拒绝执行，没有产生副作用。";
  } catch (caught) {
    error.value = safeMessage(caught);
  } finally {
    loading.value = false;
  }
}

async function onTick() {
  loading.value = true;
  error.value = null;
  try {
    const result = await tickTriggers();
    await refreshAll();
    info.value = `已检测 ${result.evaluated_count} 个触发器，生成 ${result.generated_task_ids.length} 个任务。`;
  } catch (caught) {
    error.value = safeMessage(caught);
  } finally {
    loading.value = false;
  }
}

function timelineSteps(task: Task | null, state: DynamicState | null): Array<{ title: string; text: string; status: string }> {
  if (!task) return [];
  const rows: Array<{ title: string; text: string; status: string }> = [
    {
      title: "任务规划",
      text: `已生成 ${task.steps.length} 个执行步骤。`,
      status: "SUCCESS"
    }
  ];
  task.steps
    .slice()
    .sort((left, right) => left.order - right.order)
    .forEach((step) => rows.push(stepToTimeline(step)));
  if (state?.selected_event) {
    rows.splice(2, 0, {
      title: "工具结果",
      text: `选中 ${displayValue(state.selected_event.start_time)} 的日程，目的地为 ${displayValue(state.selected_event.location)}。`,
      status: "SUCCESS"
    });
    rows.splice(3, 0, {
      title: "根据结果调整计划",
      text: "基于日程结果继续规划天气查询和路线规划。",
      status: "SUCCESS"
    });
  }
  if (task.requires_confirmation) {
    rows.push({
      title: "安全策略",
      text: `${displayRisk(task.risk_level)}，用户确认状态：${displayConfirmation(task.confirmation_status)}。`,
      status: task.confirmation_status === "CONFIRMED" ? "SUCCESS" : "PENDING"
    });
  }
  return rows;
}

function stepToTimeline(step: PlanStep) {
  const toolCall = step.tool_call;
  return {
    title: displayTool(step.tool_name),
    text: toolCall
      ? `${translateDescription(step.description)} 参数：${JSON.stringify(toolCall.arguments)}`
      : step.description,
    status: toolCall?.status ?? step.status
  };
}

function riskClass(risk: string) {
  return `risk risk-${risk.toLowerCase()}`;
}

function statusClass(status: string) {
  return `status status-${status.toLowerCase()}`;
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function displayStatus(status: string): string {
  return statusLabels[status] ?? status;
}

function displayConfirmation(status: string): string {
  return confirmationLabels[status] ?? status;
}

function displayRisk(risk: string): string {
  return riskLabels[risk] ?? risk;
}

function displayTool(toolName: string): string {
  return toolLabels[toolName] ?? toolName;
}

function displayGoal(goal: string): string {
  const labels: Record<string, string> = {
    "Resolve tomorrow morning calendar context for departure planning.": "读取明早日程，并准备通勤出发安排",
    "Send authorized notification for completed dynamic result.": "发送已授权的通勤结果提醒",
    "Unlock a mock vehicle after high-risk confirmation.": "确认安全风险后解锁模拟车辆",
    "Plan tomorrow morning commute from Psychology Institute to Baidu and estimate wake-up time.": "规划明天从心理所到百度的上班通勤，并估算起床时间"
  };
  return labels[goal] ?? goal;
}

function displayEventSummary(summary: string | null | undefined): string {
  const labels: Record<string, string> = {
    Interview: "面试",
    "Morning Meeting": "晨会"
  };
  return labels[summary ?? ""] ?? summary ?? "日程事件";
}

function displayDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}

function displayProviderName(name: string): string {
  return providerLabels[name] ?? name;
}

function displayProviderValue(value: string): string {
  return providerValueLabels[value] ?? value;
}

function translateDescription(description: string): string {
  const labels: Record<string, string> = {
    "Read tomorrow morning calendar events.": "读取明早日程",
    "Check tomorrow morning weather.": "检查明早天气",
    "Plan the commute route to the selected calendar event.": "计算到日程地点的通勤路线",
    "Send notification for dynamic result.": "发送动态规划结果通知",
    "Turn off mock living room light.": "关闭模拟客厅灯",
    "Unlock mock vehicle.": "解锁模拟车辆"
  };
  return labels[description] ?? description;
}

function metric(result: EvalBundle | null, group: "planner_v3" | "proactive_trigger_v1", key: string): string {
  const value = result?.[group]?.metrics?.[key];
  return typeof value === "number" ? value.toFixed(3) : "-";
}

function safeMessage(caught: unknown): string {
  if (!(caught instanceof Error)) return "请求失败，请稍后重试。";
  if (caught.message.includes("Failed to fetch")) {
    return "暂时无法连接服务，请检查服务状态后重试。";
  }
  if (caught.message.includes("Field required")) {
    return "任务参数不完整，请检查后重试。";
  }
  if (caught.message.includes("Tool not found")) {
    return "当前工具未注册，无法执行该操作。";
  }
  if (caught.message.includes("Unsupported planning scenario")) {
    return "当前能力不支持该请求。";
  }
  if (caught.message.includes("Planner unavailable")) {
    return "智能规划服务暂时不可用，请稍后重试。";
  }
  if (caught.message.includes("DeepSeek plan generation request failed")) {
    return "智能规划服务暂时不可用，请稍后重试。";
  }
  if (caught.message.includes("Planner output invalid")) {
    return "智能规划结果未能完整保留你的要求，本次任务没有执行。";
  }
  if (caught.message.includes("404")) {
    return "没有找到对应任务，请刷新后重试。";
  }
  return caught.message;
}

onMounted(() => {
  void refreshAll().catch((caught) => {
    error.value = safeMessage(caught);
  });
});
</script>

<template>
  <main class="workspace">
    <header class="topbar">
      <div class="brand-copy">
        <small>FlowMate</small>
        <h1>任务中心</h1>
        <p>创建、查看和确认你的生活任务。</p>
      </div>
      <div class="header-side">
        <nav class="client-nav" aria-label="体验不同设备">
          <a href="/phone">手机端</a>
          <a href="/car">车载端</a>
        </nav>
        <div class="system-strip" v-if="systemStatus">
          <span :class="statusClass(systemStatus.backend_ready ? 'SUCCESS' : 'FAILED')">服务正常</span>
          <span :class="statusClass(systemStatus.database_ready ? 'SUCCESS' : 'FAILED')">数据已连接</span>
          <span :class="statusClass(systemStatus.demo_mode ? 'SUCCESS' : 'PENDING')">安全演示模式</span>
        </div>
      </div>
    </header>

    <section class="layout">
      <section class="main-column">
        <section class="panel input-panel">
          <div class="section-heading">
            <div>
              <p class="panel-kicker">新建任务</p>
              <h2>创建一项生活任务</h2>
            </div>
            <span>用一句话说明时间、地点和要做的事</span>
          </div>
          <label class="field-label" for="task-input">任务描述</label>
          <textarea
            id="task-input"
            v-model="userInput"
            rows="2"
            placeholder="例如：明早 8:30 公司开会，帮我安排好出门并提醒我。"
          />
          <div class="preset-row" aria-label="常用任务">
            <span>常用任务</span>
            <button
              v-for="preset in presets"
              :key="preset.id"
              type="button"
              :class="{ selected: selectedPreset.id === preset.id }"
              @click="selectPreset(preset)"
            >
              {{ preset.label }}
            </button>
          </div>
          <div class="action-row">
            <button class="primary" @click="runAgent" :disabled="loading">{{ loading ? "正在创建…" : "创建任务" }}</button>
            <span v-if="info" class="info" role="status">{{ info }}</span>
            <span v-if="error" class="error" role="alert">{{ error }}</span>
          </div>
        </section>

        <section class="content-section" v-if="currentTask">
          <div class="section-heading compact">
            <h2>当前任务</h2>
            <span :class="statusClass(currentTask.status)">{{ displayStatus(currentTask.status) }}</span>
          </div>
          <div class="task-summary">
            <div>
              <span>任务目标</span>
              <strong>{{ displayGoal(currentTask.goal) }}</strong>
            </div>
            <div>
              <span>风险等级</span>
              <b :class="riskClass(currentTask.risk_level)">{{ displayRisk(currentTask.risk_level) }}</b>
            </div>
            <div>
              <span>确认状态</span>
              <strong>{{ displayConfirmation(currentTask.confirmation_status) }}</strong>
            </div>
          </div>
          <details class="technical-details">
            <summary>任务编号</summary>
            <code>{{ currentTask.id }}</code>
          </details>
        </section>

        <section class="content-section confirmation-section" v-if="confirmationTask">
          <div class="section-heading compact">
            <h2>安全确认</h2>
            <span v-if="pendingConfirmation">需要你决定后才会继续</span>
          </div>
          <div v-if="pendingConfirmation" class="confirmation">
            <div>
              <strong>这项操作可能影响设备或发送通知</strong>
              <p>风险等级：<span :class="riskClass(confirmationTask.risk_level)">{{ displayRisk(confirmationTask.risk_level) }}</span></p>
            </div>
            <div class="confirmation-actions">
              <button class="primary" @click="onConfirm" :disabled="loading">确认并继续</button>
              <button @click="onReject" :disabled="loading">暂不执行</button>
            </div>
          </div>
          <div v-else class="empty">当前任务不需要额外确认。</div>
          <div v-if="currentResponse?.notification_task && currentResponse.notification_task.id !== currentTask?.id" class="notification-summary">
            <strong>待确认通知</strong>
            <span :class="statusClass(currentResponse.notification_task.status)">
              {{ displayStatus(currentResponse.notification_task.status) }}
            </span>
            <small>{{ displayGoal(currentResponse.notification_task.goal) }}</small>
          </div>
          <details v-if="confirmationTask.steps.length" class="technical-details result-details">
            <summary>查看执行结果</summary>
            <div v-for="step in confirmationTask.steps" :key="step.id" class="result-card">
              <strong>{{ displayTool(step.tool_name) }}</strong>
              <span :class="statusClass(step.tool_call?.status ?? step.status)">
                {{ displayStatus(step.tool_call?.status ?? step.status) }}
              </span>
              <pre v-if="step.tool_call?.result">{{ JSON.stringify(step.tool_call.result, null, 2) }}</pre>
              <p v-if="step.tool_call?.error" class="error">{{ step.tool_call.error }}</p>
            </div>
          </details>
        </section>

        <section class="content-section process-section">
          <div class="section-heading compact">
            <h2>执行过程</h2>
            <span>按实际顺序记录</span>
          </div>
          <div v-if="!currentTask" class="empty">创建或选择任务后，这里会显示处理进度。</div>
          <div
            v-for="item in timelineSteps(currentTask, timelineState)"
            :key="`${item.title}-${item.text}`"
            class="timeline-row"
          >
            <span :class="statusClass(item.status)">{{ displayStatus(item.status) }}</span>
            <div>
              <strong>{{ item.title }}</strong>
              <p>{{ item.text }}</p>
            </div>
          </div>
        </section>
      </section>

      <aside class="sidebar">
        <section class="rail-section">
          <div class="section-heading compact">
            <h2>最近任务</h2>
            <button class="text-button" @click="refreshAll" :disabled="loading">刷新</button>
          </div>
          <div v-if="initialLoading" class="empty">正在加载任务…</div>
          <div v-else-if="tasks.length === 0" class="empty">还没有任务，可以先创建一项。</div>
          <button
            v-for="task in tasks.slice(0, 8)"
            :key="task.id"
            class="history-row"
            @click="chooseTask(task.id)"
          >
            <span>{{ displayGoal(task.goal) }}</span>
            <small>
              <b :class="statusClass(task.status)">{{ displayStatus(task.status) }}</b>
              <b :class="riskClass(task.risk_level)">{{ displayRisk(task.risk_level) }}</b>
            </small>
          </button>
        </section>

        <section class="rail-section">
          <div class="section-heading compact">
            <h2>自动提醒</h2>
            <button class="text-button" @click="onTick" :disabled="loading">检查现在</button>
          </div>
          <div v-if="initialLoading" class="empty">正在加载提醒…</div>
          <div v-else-if="triggers.length === 0" class="empty">目前没有待处理的自动提醒。</div>
          <div v-for="trigger in triggers" :key="trigger.id" class="trigger-row">
            <strong>{{ displayEventSummary(trigger.source_event_summary) }}</strong>
            <span>{{ trigger.source_event_location }}</span>
            <small>
              {{ displayDateTime(trigger.source_event_start) }}
              <b :class="statusClass(trigger.status)">{{ displayStatus(trigger.status) }}</b>
            </small>
          </div>
        </section>
      </aside>
    </section>

    <details class="system-details">
      <summary>
        <span>系统信息</span>
        <small>服务连接、能力验证与原始数据</small>
      </summary>
      <div class="system-grid">
        <section>
          <h2>能力质量</h2>
          <div class="metric-row"><span>场景判断准确率</span><b>{{ metric(evals, "planner_v3", "scenario_accuracy") }}</b></div>
          <div class="metric-row"><span>工具选择准确率</span><b>{{ metric(evals, "planner_v3", "tool_selection_accuracy") }}</b></div>
          <div class="metric-row"><span>参数准确率</span><b>{{ metric(evals, "planner_v3", "parameter_accuracy") }}</b></div>
          <div class="metric-row"><span>触发到期检测</span><b>{{ metric(evals, "proactive_trigger_v1", "due_detection_accuracy") }}</b></div>
          <div class="metric-row"><span>重启幂等性</span><b>{{ metric(evals, "proactive_trigger_v1", "restart_idempotency") }}</b></div>
        </section>
        <section>
          <h2>能力连接</h2>
          <div v-if="systemStatus" class="provider-list">
            <label v-for="(value, name) in systemStatus.providers" :key="name">
              <span>{{ displayProviderName(String(name)) }}</span><b>{{ displayProviderValue(value) }}</b>
            </label>
            <label v-for="(value, name) in systemStatus.integrations" :key="name">
              <span>{{ displayProviderName(String(name)) }}</span><b>{{ displayProviderValue(value.status) }}</b>
            </label>
          </div>
        </section>
        <section v-if="currentTask">
          <h2>任务原始数据</h2>
          <pre>{{ JSON.stringify(currentTask, null, 2) }}</pre>
        </section>
      </div>
    </details>
  </main>
</template>
