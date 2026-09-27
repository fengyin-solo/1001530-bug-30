<template>
  <section class="page" data-module="comm">
    <header class="page-head">
      <div>
        <h2>通信设备管理</h2>
        <p class="page-desc">维护通信设备，围绕设备编号、设备名称、设备型号、所属站点做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记通信设备</button>
        <button class="btn" type="button" @click="exportRows">导出通信设备清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>设备编号</span>
        <input v-model="keyword" placeholder="按设备编号检索" />
      </label>
      <label class="filter-item">
        <span>设备状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <section v-if="selected" class="detail-card">
      <h3>通信设备详情：{{ selected['设备编号'] }}</h3>
      <div class="detail-grid">
        <div v-for="column in columns" :key="column">
          <span class="detail-label">{{ column }}</span>
          <span>{{ selected[column] || '—' }}</span>
        </div>
        <div v-if="selected.incomplete">
          <span class="detail-label">资料标记</span>
          <span class="tag-warn">待补：{{ missingFields(selected) }}</span>
        </div>
      </div>
    </section>
    <p v-else-if="selectedArchived" class="muted">所选设备已报废归档，不在在册列表中。</p>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            {{ row[column] || '—' }}
            <span
              v-if="column === '设备编号' && row.incomplete"
              class="tag-warn"
              :title="`待补：${missingFields(row)}`"
            >资料待补</span>
          </td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">详情</button>
            <button
              v-for="action in rowActions(row)"
              :key="action"
              class="link"
              type="button"
              :disabled="acting"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
            <span v-if="!rowActions(row).length" class="muted">已归档</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无通信设备数据，可先登记通信设备</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条通信设备记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | boolean | null | string[]>

const ENDPOINT = '/api/comm'
const columns = ["设备编号", "设备名称", "设备型号", "所属站点", "安装日期", "上次检修日", "责任人", "设备状态"]
const statuses = ["待检修", "运行正常", "检修中", "已报废"]
// 与后端流转顺序保持一致：报废是终点，已报废不再出现任何动作
const FLOW: Record<string, string[]> = {
  '待检修': ['安排检修', '确认正常', '报废设备'],
  '检修中': ['确认正常', '报废设备'],
  '运行正常': ['安排检修', '报废设备'],
  '已报废': [],
}

const rows = ref<Row[]>([])
const stats = ref<{ label: string; value: number }[]>([])
const total = ref(0)
const keyword = ref('')
const statusFilter = ref('')
const errorMessage = ref('')
const noticeMessage = ref('')
const acting = ref(false)
const selectedId = ref<number | null>(null)

// 详情直接取当前列表里的同一条数据，和列表、统计卡保持同一份口径
const selected = computed(() => rows.value.find((row) => Number(row.id) === selectedId.value) ?? null)
const selectedArchived = computed(() => selectedId.value !== null && !selected.value)

function rowActions(row: Row): string[] {
  return FLOW[String(row.status ?? row['设备状态'] ?? '')] ?? []
}

function missingFields(row: Row): string {
  const fields = row['缺失字段']
  return Array.isArray(fields) && fields.length ? fields.join('、') : '设备型号、安装日期'
}

function openDetail(row: Row) {
  selectedId.value = Number(row.id)
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  errorMessage.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '通信设备登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  if (acting.value) {
    return
  }
  acting.value = true
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      const detail = typeof payload.detail === 'string' ? payload.detail : ''
      throw new Error(payload.message || detail || '通信设备动作未生效，请稍后重试')
    }
    noticeMessage.value = payload.message ?? '通信设备操作已完成'
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '通信设备操作失败'
  } finally {
    acting.value = false
  }
  await reload()
}

async function reload() {
  const query = new URLSearchParams()
  if (keyword.value.trim()) {
    query.set('keyword', keyword.value.trim())
  }
  if (statusFilter.value) {
    query.set('status', statusFilter.value)
  }
  try {
    const [listResponse, statsResponse] = await Promise.all([
      request(`${ENDPOINT}?${query.toString()}`),
      request(`${ENDPOINT}/stats`),
    ])
    if (!listResponse.ok) {
      throw new Error('通信设备列表读取失败')
    }
    if (!statsResponse.ok) {
      throw new Error('通信设备统计读取失败')
    }
    const payload = await listResponse.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    const statsPayload = await statsResponse.json()
    stats.value = statsPayload.cards ?? []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '通信设备列表读取失败'
  }
}

onMounted(reload)
</script>
