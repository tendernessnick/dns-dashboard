// 10_theme.js —— 渲染器：板块主题色（m1-m5 → --acc CSS变量）
['m1','m2','m3','m4','m5'].forEach(function(id){
  var s=document.getElementById(id); if(s) s.style.setProperty('--acc', ACCENT[id]);
});
