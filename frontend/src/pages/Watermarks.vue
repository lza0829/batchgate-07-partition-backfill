<script setup>
import { onMounted, ref } from 'vue'
import { getJSON } from '../api'
const mainRows = ref([])
const partRows = ref([])
const partitionFilter = ref('')
const err = ref('')

async function refresh() {
  err.value = ''
  try {
    mainRows.value = await getJSON('/api/watermarks')
    const q = partitionFilter.value.trim()
    partRows.value = await getJSON(
      q ? `/api/partition-watermarks?partition=${encodeURIComponent(q)}` : '/api/partition-watermarks'
    )
  } catch (e) { err.value = String(e.message || e) }
}

onMounted(refresh)
</script>
<template>
  <div class="page">
    <h1>产出水位</h1>
    <p class="muted">
      主水位每作业一行，仅正常编排推进；分区水位按（作业, 分区）记录，仅回补编排写入，两者互不影响。
    </p>
    <p v-if="err" class="tag danger">{{ err }}</p>

    <div class="panel">
      <h3>主水位（正常编排）</h3>
      <table>
        <thead><tr><th>作业</th><th>watermark</th><th>行数</th><th>更新</th></tr></thead>
        <tbody>
          <tr v-for="w in mainRows" :key="w.job_id">
            <td class="mono">{{ w.job_name }}</td>
            <td class="mono">{{ w.watermark_ts || '—' }}</td>
            <td>{{ w.artifact_rows }}</td>
            <td class="mono">{{ w.updated_at || '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="panel">
      <h3>分区水位（回补编排）</h3>
      <div class="filter-bar">
        <label>
          分区过滤
          <input v-model="partitionFilter" placeholder="如 2026-11-08，留空看全部" @change="refresh" style="width:16rem" />
        </label>
        <button class="secondary" @click="refresh">刷新</button>
        <span class="muted">共 {{ partRows.length }} 条分区记录</span>
      </div>
      <table>
        <thead><tr><th>分区</th><th>作业</th><th>分区 watermark</th><th>行数</th><th>更新</th></tr></thead>
        <tbody>
          <tr v-if="partRows.length === 0">
            <td colspan="5" class="muted">暂无分区水位，可到编排台发起带分区的回补。</td>
          </tr>
          <tr v-for="p in partRows" :key="`${p.job_id}-${p.partition}`">
            <td class="mono">{{ p.partition }}</td>
            <td class="mono">{{ p.job_name }}</td>
            <td class="mono">{{ p.watermark_ts || '—' }}</td>
            <td>{{ p.artifact_rows }}</td>
            <td class="mono">{{ p.updated_at || '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
<style scoped>
.filter-bar { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem; flex-wrap: wrap; }
</style>
