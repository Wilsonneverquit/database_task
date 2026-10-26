<template>
  <el-result :icon="route.meta.notFound ? 'info' : 'warning'" :title="route.meta.notFound ? '页面不存在' : '当前角色无权访问该页面'"
    :sub-title="route.meta.notFound ? '请检查地址是否正确' : '页面按角色授权（《前端交接文档》第十节），如需访问请联系系统管理员分配角色'">
    <template #extra>
      <el-button type="primary" @click="router.replace('/')">返回首页</el-button>
    </template>
  </el-result>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
</script>
