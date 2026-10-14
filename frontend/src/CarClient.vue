<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import {
  acceptHandoff,
  getDevice,
  getTaskDeviceState,
  heartbeatDevice,
  listIncomingHandoffs,
  rejectHandoff,
  seedCrossDeviceDemo
} from "./api/crossDevice";
import type { Device, Handoff, TaskDeviceState } from "./types";

const deviceId = "car_001";
const device = ref<Device | null>(null);
const incoming = ref<Handoff[]>([]);
const selected = ref<Handoff | null>(null);
const deviceState = ref<TaskDeviceState | null>(null);
const error = ref("");
const info = ref("");
const busy = ref(false);
let pollTimer: number | undefined;
let heartbeatTimer: number | undefined;

const handoff = computed(() => selected.value ?? incoming.value[0] ?? null);

const statusLabels: Record<string, string> = {
  PENDING: "等待确认",
  ACCEPTED: "已接力",
  REJECTED: "已拒绝",
  ONLINE: "在线",
  OFFLINE: "离线"
};

function displayStatus(status: string) {
  return statusLabels[status] ?? status;
}

function displayGoal(goal: string) {
  return goal === "Resolve tomorrow morning calendar context for departure planning."
    ? "读取明早日程，并继续完成通勤出发安排"
    : goal;
}

function displayNavigationSummary(summary: string | null | undefined) {
  if (!summary) return "路线信息已准备";
  return summary
    .replace("km", "公里")
    .replace("min", "分钟")
    .replace("traffic heavy", "路况拥堵")
    .replaceAll(",", " ·");
}

function friendlyError(caught: unknown) {
  const message = caught instanceof Error ? caught.message : String(caught);
  if (message.includes("Failed to fetch")) return "暂时无法连接本地服务，请稍后重试。";
  if (message.includes("version")) return "任务已在另一台设备更新，正在重新同步。";
  return message;
}

async function refresh() {
  device.value = await getDevice(deviceId);
  const rows = await listIncomingHandoffs(deviceId);
  incoming.value = rows;
  if (!selected.value || selected.value.status === "PENDING") {
    selected.value = rows.find((item) => item.status === "PENDING") ?? rows[0] ?? selected.value;
  }
  if (handoff.value) {
    deviceState.value = await getTaskDeviceState(handoff.value.task_id);
  }
}

async function heartbeatAndRefresh() {
  device.value = await heartbeatDevice(deviceId);
  await refresh();
}

async function accept() {
  if (!handoff.value || !deviceState.value) return;
  busy.value = true;
  error.value = "";
  try {
    selected.value = await acceptHandoff(
      handoff.value.handoff_id,
      deviceId,
      deviceState.value.version
    );
    info.value = "任务已接力到车载端，手机将在下一次同步时看到更新。";
    await refresh();
  } catch (caught) {
    error.value = friendlyError(caught);
  } finally {
    busy.value = false;
  }
}

async function reject() {
  if (!handoff.value || !deviceState.value) return;
  busy.value = true;
  error.value = "";
  try {
    selected.value = await rejectHandoff(
      handoff.value.handoff_id,
      deviceId,
      deviceState.value.version
    );
    info.value = "已拒绝接力，任务仍保留在手机端。";
    await refresh();
  } catch (caught) {
    error.value = friendlyError(caught);
  } finally {
    busy.value = false;
  }
}

onMounted(async () => {
  try {
    await seedCrossDeviceDemo();
    await heartbeatAndRefresh();
  } catch (caught) {
    error.value = friendlyError(caught);
  }
  pollTimer = window.setInterval(() => void refresh(), 2000);
  heartbeatTimer = window.setInterval(() => void heartbeatDevice(deviceId), 4000);
});

onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer);
  if (heartbeatTimer) window.clearInterval(heartbeatTimer);
});
</script>

<template>
  <main class="car-shell" translate="no">
    <header class="car-header">
      <div>
        <small>FlowMate 车载端</small>
        <h1>通勤接力</h1>
        <p>查看从手机同步的行程和任务</p>
      </div>
      <div class="presence">
        <i :class="device?.status === 'ONLINE' ? 'online' : ''"></i>
        <span>车载端</span>
        <b>{{ displayStatus(device?.status ?? "OFFLINE") }}</b>
      </div>
    </header>

    <section v-if="handoff" class="car-console">
      <div class="incoming-label"><span>手机端发来的通勤任务</span><b>{{ displayStatus(handoff.status) }}</b></div>
      <div class="route-hero">
        <div>
          <span>会议时间</span>
          <strong>{{ handoff.context.meeting_start ?? "08:30" }}</strong>
          <p>{{ handoff.context.meeting_summary === "Morning Meeting" ? "晨会" : (handoff.context.meeting_summary ?? "晨会") }}</p>
        </div>
        <div class="arrow">→</div>
        <div>
          <span>目的地</span>
          <strong>{{ handoff.context.destination ?? "-" }}</strong>
          <p>{{ displayNavigationSummary(handoff.context.navigation_summary) }}</p>
        </div>
      </div>

      <div class="context-panel">
        <div class="context-kicker">通勤安排已同步</div>
        <h2>{{ displayGoal(handoff.context.goal) }}</h2>
        <p>手机端的会议和路线信息已经带到车上，可以从这里继续。</p>
      </div>

      <div class="car-actions" v-if="handoff.status === 'PENDING'">
        <button class="accept" :disabled="busy" @click="accept">接受并继续任务</button>
        <button class="reject" :disabled="busy" @click="reject">暂不接力</button>
      </div>
      <div class="accepted-banner" v-else-if="handoff.status === 'ACCEPTED'">
        <b>接力完成</b><span>这项任务现在由车载端继续处理</span>
      </div>
      <p v-if="info" class="car-info" role="status">{{ info }}</p>
      <p v-if="error" class="car-error" role="alert">{{ error }}</p>

      <details class="car-technical">
        <summary>任务详情</summary>
        <dl>
          <dt>来自设备</dt><dd>手机端 · <code>{{ handoff.source_device }}</code></dd>
          <dt>任务编号</dt><dd><code>{{ handoff.task_id }}</code></dd>
          <dt>任务版本</dt><dd>{{ deviceState?.version ?? handoff.task_version }}</dd>
          <dt>接力编号</dt><dd><code>{{ handoff.handoff_id }}</code></dd>
        </dl>
      </details>
    </section>

    <section v-else class="waiting-console">
      <div class="radar"></div>
      <h2>等待手机端任务</h2>
      <p>在手机端创建通勤任务，FlowMate 会在适合时推荐接力到车辆。</p>
      <small>任务会自动同步，无需手动刷新。</small>
      <p v-if="error" class="car-error" role="alert">{{ error }}</p>
    </section>

    <footer>
      <span>网页模拟器 · 不控制真实车辆</span>
      <span>导航与车辆状态均为演示数据</span>
    </footer>
  </main>
</template>

<style scoped src="./car.css"></style>
