<template>
  <g transform="scale(.31)" pointer-events="none" :aria-label="profile.short">
    <path d="M -30 -16 L -22 -28 L 7 -31 L 29 -15 L 30 15 L 12 29 L -20 27 Z" :fill="profile.ground"/>
    <rect v-for="(p,i) in plan.patches" :key="`p${i}`" :x="p.x-p.w/2" :y="p.z-p.d/2" :width="p.w" :height="p.d" :fill="p.color"/>
    <g v-for="(r,i) in plan.rings" :key="`r${i}`"><ellipse :cx="r.x" :cy="r.z" :rx="r.a" :ry="r.b" :fill="r.color"/><ellipse :cx="r.x" :cy="r.z" :rx="r.innerA" :ry="r.innerB" fill="#8bb578"/></g>
    <path v-for="(p,i) in plan.paths" :key="`s${i}`" :d="'M '+p.points.map(([x,z])=>`${x} ${z}`).join(' L ')" fill="none" :stroke="p.color" :stroke-width="p.width"/>
    <path v-if="profile.kind==='riverside'" d="M -18 -33 Q -24 0 -17 33" fill="none" stroke="#7dc5d3" stroke-width="8"/>
    <rect v-for="(b,i) in plan.boxes" :key="`b${i}`" :x="b.x-b.w/2" :y="b.z-b.d/2" :width="b.w" :height="b.d" :fill="b.glass?'#97b8c3':b.color" stroke="#9caeaa" stroke-width=".5"/>
    <rect v-for="(r,i) in plan.roofs" :key="`f${i}`" :x="r.x-r.w/2" :y="r.z-r.d/2" :width="r.w" :height="r.d" :fill="r.color"/>
    <circle v-for="(t,i) in plan.trees" :key="`t${i}`" :cx="t.x" :cy="t.z" :r="t.r" fill="#82a866"/>
  </g>
</template>
<script setup>
import {computed} from 'vue'
import {areaLandmark} from '@/utils/area-landmarks'
import {landmarkParts} from '@/utils/landmark-parts'
const props=defineProps({area:{type:Object,required:true}})
const profile=computed(()=>areaLandmark(props.area))
const plan=computed(()=>landmarkParts(profile.value.kind))
</script>
