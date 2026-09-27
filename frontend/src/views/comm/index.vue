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
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>缺项标记</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td>
            <span v-if="row.缺项标记" class="mark-tag">缺{{ row.缺项标记 }}</span>
            <span v-else>—</span>
          </td>
          <td class="row-actions">
            <button
              v-for="action in allowedActions(row)"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
            <button class="link" type="button" @click="openDetail(row)">详情</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 2" class="empty-state">暂无通信设备数据，可先登记通信设备</td>
        </tr>
      </tbody>
    </table>

    <section v-if="detail" class="detail-panel">
      <header class="detail-head">
        <h3>通信设备详情</h3>
        <button class="btn ghost" type="button" @click="detail = null">关闭</button>
      </header>
      <dl class="detail-grid">
        <template v-for="field in detailFields" :key="field">
          <dt>{{ field }}</dt>
          <dd>{{ detail[field] ?? '—' }}</dd>
        </template>
        <dt>缺项标记</dt>
        <dd>
          <span v-if="detail.缺项标记" class="mark-tag">缺{{ detail.缺项标记 }}</span>
          <span v-else>—</span>
        </dd>
      </dl>
    </section>

    <footer class="page-foot">
      <span>共 {{ total }} 条通信设备记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/comm'
const columns = ["设备编号", "设备名称", "设备型号", "所属站点", "安装日期", "上次检修日", "责任人", "设备状态"]
const actions = ["安排检修", "确认正常", "报废设备"]
const statuses = ["待检修", "运行正常", "检修中", "已报废"]
const actionTargets: Record<string, string> = { 安排检修: '检修中', 确认正常: '运行正常', 报废设备: '已报废' }
const detailFields = [...columns]

const rows = ref<Row[]>([])
const stats = ref<{ label: string; value: number }[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)
const detail = ref<Row | null>(null)

// 状态只能按 待检修 → 运行正常 → 检修中 → 已报废 顺序前进，已报废归档后不再出现
function allowedActions(row: Row) {
  const current = statuses.indexOf(String(row.status ?? ''))
  return actions.filter((action) => statuses.indexOf(actionTargets[action]) > current)
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '通信设备登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message ?? payload.detail ?? '通信设备动作未生效，请稍后重试')
    }
    if (detail.value && String(detail.value.id) === String(row.id)) {
      detail.value = payload.ok ? payload.entry : null
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '通信设备操作失败'
  }
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error('通信设备详情读取失败，可能已报废归档')
    }
    detail.value = await response.json()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '通信设备详情读取失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const [listResponse, statsResponse] = await Promise.all([
      request(`${ENDPOINT}?${query}`),
      request(`${ENDPOINT}/stats`),
    ])
    if (!listResponse.ok || !statsResponse.ok) {
      throw new Error('通信设备列表读取失败')
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

<style scoped>
.detail-panel {
  margin-top: 12px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 16px;
}
.detail-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.detail-head h3 {
  margin: 0;
  font-size: 14px;
}
.detail-grid {
  display: grid;
  grid-template-columns: 120px 1fr 120px 1fr;
  gap: 6px 12px;
  margin: 10px 0 0;
  font-size: 13px;
}
.detail-grid dt {
  color: var(--muted);
}
.detail-grid dd {
  margin: 0;
}
.mark-tag {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 10px;
  background: #fef3c7;
  color: #b45309;
  font-size: 12px;
}
</style>
