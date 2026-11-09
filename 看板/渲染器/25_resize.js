// 25_resize.js —— 全局：窗口变化后重绘图表（依赖 15_chart/20_share 的 charts/shareEls）
// v14：折线重绘传 redraw=true，不重播入场动画
// v18.8：隐藏co-panel内图表clientWidth=0会按300px兜底画错尺寸——只重绘可见图（切tab时40_copanel自会重绘）
function vis(el){var p=el.closest('[data-copanel]');return (!p||!p.hidden)&&el.clientWidth>0}
var rT;window.addEventListener('resize',function(){clearTimeout(rT);
  rT=setTimeout(function(){
    charts.forEach(function(el){if(vis(el))drawChart(el,true)});
    shareEls.forEach(function(el){if(vis(el))drawShare(el)});
  },150)});
