<script setup>
import { onMounted, ref } from 'vue'
import { getJSON, postJSON } from '../api'
const history = ref([])
const last = ref(null)
const busy = ref(false)
const err = ref('')
const partitionInput = ref('2026-11-08')

async function refresh() { history.value = await getJSON('/api/orchestrations') }

async function runOnce(mode) {
  err.value = ''
  const partition = mode === 'backfill' ? partitionInput.value.trim() : null
  if (mode === 'backfill' && !partition) {
    err.value = '回补必须填写分区标识（如业务日 2026-11-08）'
    return
  }
  busy.value = true
  try {
    last.value = await postJSON('/api/orchestrations', partition ? { partition } : {})
    await refresh()
  } catch (e) { err.value = String(e.message || e) }
  finally { busy.value = false }
}

function modeTag(o) {
  return o.mode === 'backfill' ? `回补 · ${o.partition}` : '正常'
}

onMounted(async () => {
  try { await refresh() } catch (e) { err.value = String(e.message || e) }
})
</script>
<template>
  <div class="page">
    <h1>编排台</h1>
    <p class="muted">
      正常编排按依赖层执行并推进各作业主水位；回补编排带分区标识（业务日）执行，
      只写分区水位，不抬主水位。上游未成功则下游记 skipped_dep。
    </p>
    <div class="panel">
      <div class="run-bar">
        <button :disabled="busy" @click="runOnce('normal')">
          {{ busy ? '编排中…' : '执行正常编排' }}
        </button>
        <span class="run-divider">回补</span>
        <input v-model="partitionInput" placeholder="分区标识，如 2026-11-08" style="width:15rem" />
        <button class="secondary" :disabled="busy" @click="runOnce('backfill')">
          {{ busy ? '编排中…' : '按分区回补' }}
        </button>
      </div>
    </div>
    <p v-if="err" class="tag danger">{{ err }}</p>
    <div class="panel" v-if="last">
      <h3>最近一次报告</h3>
      <p>
        #{{ last.id }} ·
        <span class="tag" :class="last.mode==='backfill' ? 'warn' : 'ok'">{{ modeTag(last) }}</span> ·
        <span class="tag" :class="last.status==='ok' ? 'ok' : 'danger'">{{ last.status }}</span> ·
        succeeded {{ last.report?.succeeded }} /
        failed {{ last.report?.failed }} /
        skipped {{ last.report?.skipped }} /
        attempts {{ last.report?.attempt_count }}
      </p>
      <p class="mono muted">
        mode={{ last.report?.mode }} partition={{ last.report?.partition ?? '—' }}
        watermarked_jobs={{ last.report?.watermarked_jobs }}
        partition_watermarked_jobs={{ last.report?.partition_watermarked_jobs ?? 0 }}
        layers={{ last.report?.layer_count }}
      </p>
      <p>
        <router-link :to="{ path: '/attempts', query: { orchestration_id: last.id } }">查看本次尝试 →</router-link>
        ·
        <router-link to="/watermarks">
          {{ last.mode === 'backfill' ? '分区水位 →' : '主水位 →' }}
        </router-link>
      </p>
    </div>
    <div class="panel">
      <h3>历史编排</h3>
      <table>
        <thead>
          <tr><th>ID</th><th>模式 / 分区</th><th>状态</th><th>成功</th><th>失败</th><th>跳过</th><th>开始</th></tr>
        </thead>
        <tbody>
          <tr v-for="o in history" :key="o.id">
            <td>{{ o.id }}</td>
            <td><span class="tag" :class="o.mode==='backfill' ? 'warn' : 'ok'">{{ modeTag(o) }}</span></td>
            <td>{{ o.status }}</td>
            <td>{{ o.report?.succeeded }}</td>
            <td>{{ o.report?.failed }}</td>
            <td>{{ o.report?.skipped }}</td>
            <td class="mono">{{ o.started_at }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
<style scoped>
.run-bar { display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; }
.run-divider { color: var(--muted); font-size: 0.9rem; }
</style>
