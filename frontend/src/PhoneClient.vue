<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import {
  createHandoff,
  getDeviceRoute,
  getTaskDeviceState,
  heartbeatDevice,
  initializeTaskDeviceState,
  listTaskHandoffs,
  listUserDevices,
  seedCrossDeviceDemo
} from "./api/crossDevice";
import { createDemoTask, getTask } from "./api/tasks";
import type { Device, Handoff, RoutingDecision, Task, TaskDeviceState } from "./types";

const userId = "demo_user";
const deviceId = "phone_001";
const userInput = ref("明早 8:30 公司开会，帮我安排出门");
const task = ref<Task | null>(null);
const deviceState = ref<TaskDeviceState | null>(null);
const route = ref<RoutingDecision | null>(null);
const handoffs = ref<Handoff[]>([]);
const devices = ref<Device[]>([]);
const error = ref("");
const info = ref("");
const busy = ref(false);
let pollTimer: number | undefined;
let heartbeatTimer: number | undefined;

const latestHandoff = computed(() => handoffs.value[0] ?? null);

const statusLabels: Record<string, string> = {
  CREATED: "已创建",
  PLANNED: "已规划",
  WAITING_CONFIRMATION: "等待确认",
  EXECUTING: "执行中",
  COMPLETED: "已完成",
  FAILED: "执行失败",
  PENDING: "等待接收",
  ACCEPTED: "已接力",
  REJECTED: "已拒绝",
  SUCCESS: "成功",
  ONLINE: "在线",
  OFFLINE: "离线"
};

const toolLabels: Record<string, string> = {
  calendar_tool: "读取日程",
  weather_tool: "查询天气",
  navigation_tool: "规划路线",
  notification_tool: "发送提醒"
};

function displayStatus(status: string) {
  return statusLabels[status] ?? status;
}

function displayGoal(goal: string) {
  const labels: Record<string, string> = {
    "Resolve tomorrow morning calendar context for departure planning.": "读取明早日程，并准备通勤出发安排",
    "Send authorized notification for completed dynamic result.": "发送已授权的通勤结果提醒"
  };
  return labels[goal] ?? goal;
}

function displayDeviceType(type: string) {
  return type === "PHONE" ? "手机端" : type === "CAR" ? "车载端" : type;
}

function displayRouteReason(decision: RoutingDecision) {
  if (!decision.available) return "当前没有适合接力的在线设备。";
  const deviceName = decision.recommended_device === "car_001" ? "车载端" : decision.recommended_device;
  return `${deviceName}当前在线，可以继续显示路线和行程。`;
}

function displayTime(value: string | null | undefined) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  }).format(new Date(value));
}

function friendlyError(caught: unknown) {
  const message = caught instanceof Error ? caught.message : String(caught);
  if (message.includes("Failed to fetch")) return "暂时无法连接本地服务，请稍后重试。";
  return message;
}

async function bootstrap() {
  await seedCrossDeviceDemo();
  await heartbeatDevice(deviceId);
  devices.value = await listUserDevices(userId);
}

async function createMorningCommute() {
  busy.value = true;
  error.value = "";
  info.value = "";
  try {
    const response = await createDemoTask("morning_commute", userInput.value);
    if (!response.task) throw new Error("通勤任务创建失败，请稍后重试。");
    task.value = response.task;
    deviceState.value = await initializeTaskDeviceState(
      task.value.id,
      userId,
      deviceId
    );
    route.value = await getDeviceRoute(task.value.id);
    handoffs.value = await listTaskHandoffs(task.value.id);
    info.value = "通勤任务已创建，正在为你寻找适合接力的设备。";
  } catch (caught) {
    error.value = friendlyError(caught);
  } finally {
    busy.value = false;
  }
}

async function refreshCoordination() {
  if (!task.value) return;
  const taskId = task.value.id;
  const [nextTask, nextState, nextRoute, nextHandoffs, nextDevices] = await Promise.all([
    getTask(taskId),
    getTaskDeviceState(taskId),
    getDeviceRoute(taskId),
    listTaskHandoffs(taskId),
    listUserDevices(userId)
  ]);
  task.value = nextTask;
  deviceState.value = nextState;
  route.value = nextRoute;
  handoffs.value = nextHandoffs;
  devices.value = nextDevices;
}

async function requestHandoff() {
  if (!task.value || !deviceState.value) return;
  busy.value = true;
  error.value = "";
  try {
    const handoff = await createHandoff(task.value.id, deviceState.value.version);
    info.value = "接力请求已发送到车载端，等待车辆确认。";
    await refreshCoordination();
  } catch (caught) {
    error.value = friendlyError(caught);
  } finally {
    busy.value = false;
  }
}

onMounted(async () => {
  try {
    await bootstrap();
  } catch (caught) {
    error.value = friendlyError(caught);
  }
  pollTimer = window.setInterval(() => void refreshCoordination(), 2000);
  heartbeatTimer = window.setInterval(() => void heartbeatDevice(deviceId), 4000);
});

onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer);
  if (heartbeatTimer) window.clearInterval(heartbeatTimer);
});
</script>

<template>
  <main class="phone-shell" translate="no">
    <header>
      <div class="brand-block">
        <small>FlowMate</small>
        <h1>通勤任务</h1>
        <p>在手机上创建任务，需要时接力到车载端。</p>
      </div>
      <div class="device-pill">
        <span class="presence-dot"></span>
        <div><small>当前设备</small><b>手机端 · 在线</b></div>
        <code>phone_001</code>
      </div>
    </header>

    <nav v-if="task" class="journey-steps" aria-label="跨设备任务进度">
      <span :class="{ active: task }"><b>1</b> 手机创建任务</span>
      <span :class="{ active: latestHandoff }"><b>2</b> 发给车载端</span>
      <span :class="{ active: latestHandoff?.status === 'ACCEPTED' }"><b>3</b> 车辆继续执行</span>
    </nav>

    <section class="phone-grid">
      <article class="phone-card create-card">
        <div class="section-kicker">新建任务</div>
        <h2>创建通勤任务</h2>
        <label for="commute-input">任务描述</label>
        <textarea id="commute-input" v-model="userInput" rows="2" placeholder="写清时间、地点和要做的事" />
        <button class="phone-primary" :disabled="busy" @click="createMorningCommute">
          {{ busy ? "正在创建…" : "创建任务" }}
        </button>
        <p v-if="info" class="phone-info" role="status">{{ info }}</p>
        <p v-if="error" class="phone-error" role="alert">{{ error }}</p>
      </article>

      <article class="phone-card" v-if="task && deviceState">
        <div class="card-heading">
          <div><div class="section-kicker">当前进度</div><h2>通勤任务</h2></div>
          <span class="status-chip success">{{ displayStatus(task.status) }}</span>
        </div>
        <dl>
          <dt>任务目标</dt><dd>{{ displayGoal(task.goal) }}</dd>
          <dt>当前设备</dt><dd class="owner">{{ displayDeviceType(deviceState.current_device_id === deviceId ? "PHONE" : "CAR") }}</dd>
        </dl>
        <details class="technical-details">
          <summary>任务详情</summary>
          <p>任务编号：<code>{{ task.id }}</code></p>
          <p>发起设备：<code>{{ deviceState.origin_device_id }}</code></p>
          <p>版本：{{ deviceState.version }}</p>
        </details>
      </article>

      <article class="phone-card" v-if="route && deviceState">
        <div class="card-heading">
          <div><div class="section-kicker">继续行程</div><h2>发送到车载端</h2></div>
          <span :class="route.available ? 'ok' : 'muted'">
            {{ route.available ? "可接力" : "等待设备" }}
          </span>
        </div>
        <p class="supporting-copy">{{ displayRouteReason(route) }}</p>
        <button
          class="phone-primary"
          :disabled="busy || !route.available || latestHandoff?.status === 'PENDING' || deviceState.current_device_id !== deviceId"
          @click="requestHandoff"
        >
          {{ latestHandoff?.status === "PENDING" ? "等待车辆确认" : "接力到车载端" }}
        </button>
      </article>

      <article class="phone-card timeline" v-if="latestHandoff">
        <div class="section-kicker">设备接力</div>
        <h2>当前状态</h2>
        <p><b>接力方向</b><span>手机端 → 车载端</span></p>
        <p><b>当前状态</b><span>{{ displayStatus(latestHandoff.status) }}</span></p>
        <p v-if="latestHandoff.accepted_at"><b>接收时间</b><span>{{ displayTime(latestHandoff.accepted_at) }}</span></p>
      </article>

      <details class="phone-details" v-if="task">
        <summary>查看执行记录</summary>
        <ol class="trace-list">
          <li v-for="step in task.steps" :key="step.id">
            <span>{{ step.order }}</span>
            <div><b>{{ toolLabels[step.tool_name] ?? step.tool_name }}</b><small>{{ displayStatus(step.status) }}</small></div>
          </li>
        </ol>
      </details>

      <section class="device-section">
        <div class="section-kicker">设备状态</div>
        <h2>可用设备</h2>
        <div v-for="device in devices" :key="device.id" class="device-row">
          <span><b>{{ displayDeviceType(device.device_type) }}</b><small>{{ device.id }}</small></span>
          <b :class="device.status === 'ONLINE' ? 'ok' : 'muted'">{{ displayStatus(device.status) }}</b>
        </div>
      </section>
    </section>
  </main>
</template>

<style scoped src="./phone.css"></style>
