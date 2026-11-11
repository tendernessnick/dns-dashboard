// 10_theme.js —— 渲染器：板块主题色（m1-m5 → --acc CSS变量）
root.querySelectorAll('.mod[id]').forEach(function(s){
  s.style.setProperty('--acc',getComputedStyle(s).getPropertyValue('--section-accent').trim()||ACCENT[s.id]||'#285FAF');
});
