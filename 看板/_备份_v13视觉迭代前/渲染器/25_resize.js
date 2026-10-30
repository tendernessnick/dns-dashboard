// 25_resize.js —— 全局：窗口变化后重绘所有图表（依赖 15_chart/20_share 的 charts/shareEls）
var rT;window.addEventListener('resize',function(){clearTimeout(rT);
  rT=setTimeout(function(){charts.forEach(drawChart);shareEls.forEach(drawShare)},150)});
