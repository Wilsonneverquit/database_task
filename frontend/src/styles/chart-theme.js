// Visual foundation informed by Unslop (Damir Sokolovsky, CC BY 4.0).
// Shared graphite chart surfaces. Heatmap labels use their own dark ink on filled cells.
export const chartPalette = {
  ink:'#e7eef8', muted:'#9aaac0', grid:'#29394f', low:'#aec7c4',
  mid:'#d9b474', high:'#b34f4d', accent:'#78aaff', blank:'#28384d', cellInk:'#142333',
}
export const chartTheme = {
  backgroundColor:'transparent',
  color:[chartPalette.accent,chartPalette.mid,'#ee8d87','#8bcba5','#42c6d6'],
  textStyle:{fontFamily:'Segoe UI, Microsoft YaHei, sans-serif',fontSize:12,color:chartPalette.muted},
  title:{textStyle:{color:chartPalette.ink},subtextStyle:{color:chartPalette.muted}},
  legend:{textStyle:{color:chartPalette.muted,fontSize:12},inactiveColor:'#64758d',itemWidth:12,itemHeight:8,itemGap:20},
  tooltip:{backgroundColor:'#18263a',borderColor:'#3a506e',borderWidth:1,padding:[12,16],textStyle:{color:chartPalette.ink,fontSize:12},extraCssText:'box-shadow:0 10px 28px #02071266;border-radius:10px;line-height:1.8;'},
  categoryAxis:{nameTextStyle:{color:chartPalette.muted},axisLine:{lineStyle:{color:'#435873'}},axisTick:{show:false},axisLabel:{color:chartPalette.muted,fontSize:11},splitLine:{lineStyle:{color:chartPalette.grid}},splitArea:{areaStyle:{color:['#132033','#18263a']}}},
  valueAxis:{nameTextStyle:{color:chartPalette.muted},axisLine:{show:false},axisLabel:{color:chartPalette.muted,fontSize:11},splitLine:{lineStyle:{color:chartPalette.grid}}},
  visualMap:{textStyle:{color:chartPalette.muted,fontSize:11},itemWidth:10,itemHeight:10,itemGap:20},
  dataZoom:{backgroundColor:'#0e1828',borderColor:'#334760',fillerColor:'#4d8fff26',textStyle:{color:chartPalette.muted},handleStyle:{color:'#78aaff',borderColor:'#94bdff'},dataBackground:{lineStyle:{color:'#4f6786'},areaStyle:{color:'#233b5d'}},selectedDataBackground:{lineStyle:{color:'#78aaff'},areaStyle:{color:'#355e91'}}},
  pie:{label:{color:chartPalette.ink},labelLine:{lineStyle:{color:'#6d83a0'}},itemStyle:{borderColor:'#121d2d',borderWidth:2}},
}
