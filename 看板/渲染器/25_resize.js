// 25_resize.js —— 全局：窗口变化后重绘所有图表（依赖 15_chart/20_share 的 charts/shareEls）
// v14：折线重绘传 redraw=true，不重播入场动画
var rT;window.addEventListener('resize',function(){clearTimeout(rT);
  rT=setTimeout(function(){charts.forEach(function(el){drawChart(el,true)});shareEls.forEach(drawShare)},150)});
