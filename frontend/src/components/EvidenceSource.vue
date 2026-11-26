<template>
  <aside class="source-inspector" aria-label="当前证据来源">
    <header><el-icon><Document /></el-icon><h3>来源详情</h3></header>
    <template v-if="source?.node">
      <h4>{{source.node.title}}</h4><p class="source-time mono">{{source.node.event_at}}</p>
      <p>{{source.node.explanation}}</p>
      <dl class="record"><template v-for="(value,key) in source.node.source_record||{}" :key="key"><dt>{{key}}</dt><dd>{{value??'—'}}</dd></template></dl>
      <p v-if="!Object.keys(source.node.source_record||{}).length" class="muted">此节点暂无对应原始记录，请查看关联理由。</p>
      <section v-if="source.node.driver_record"><h4>独立观察</h4><p>{{source.node.driver_record.source_type}} · {{source.node.driver_record.observed_at}}</p></section>
      <section v-if="source.edges.length"><h4>关联理由</h4><p v-for="e in source.edges" :key="e.edge_id">{{e.reason}}</p></section>
      <router-link v-if="source.node.score_id" :to="{name:'risk-detail',params:{scoreId:source.node.score_id}}">查看评分解释 →</router-link>
    </template><p v-else class="muted">选择事件，再点击时间轴中的“查看来源”。</p>
  </aside>
</template>
<script setup>
defineProps({source:{type:Object,default:null}})
</script>
<style scoped>
.source-inspector{min-width:0;position:sticky;top:0;padding:22px;background:var(--surface);border:1px solid var(--card-border);border-radius:12px;max-height:calc(100dvh - 165px);overflow:auto;overscroll-behavior:contain;scrollbar-gutter:stable}.source-inspector header{display:flex;gap:10px;align-items:center;padding-bottom:18px;border-bottom:1px solid var(--border-soft);color:var(--accent-ink)}.source-inspector h3{font-size:16px;font-weight:500;margin:0;color:var(--text-primary)}.source-inspector h4{font-size:14px;font-weight:500;line-height:1.7;margin:20px 0 8px}.source-inspector p{font-size:12px;line-height:1.85;color:var(--text-secondary);overflow-wrap:anywhere}.source-time{color:var(--text-muted)!important}.record{display:grid;gap:5px;margin:20px 0;font-size:12px;line-height:1.8}.record dt{color:var(--text-muted);margin-top:8px;font-family:var(--font-mono);overflow-wrap:anywhere}.record dd{margin:0;color:var(--text-primary);overflow-wrap:anywhere}.source-inspector a{display:inline-block;font-size:12px;margin-top:16px}@media(max-width:1100px){.source-inspector{position:static;max-height:none;grid-column:2}}@media(max-width:800px){.source-inspector{grid-column:auto;padding:16px}}
</style>
