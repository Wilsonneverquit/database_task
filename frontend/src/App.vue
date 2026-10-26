<template>
  <router-view v-if="route.meta.bare" />
  <AppLayout v-else>
    <router-view />
  </AppLayout>
</template>

<script setup>
import { useRoute } from 'vue-router'
import AppLayout from '@/components/AppLayout.vue'

const route = useRoute()
</script>
