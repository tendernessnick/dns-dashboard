// 40_copanel.js —— 渲染器：上市公司切换面板（.cotab → .co-panel 显隐+重绘）
var cotabs=[].slice.call(root.querySelectorAll('[data-cotab]'));
cotabs.forEach(function(b){
  b.addEventListener('click',function(){
    var scope=b.closest('.mod')||root;
    scope.querySelectorAll('[data-cotab]').forEach(function(x){x.classList.toggle('on',x===b);x.setAttribute('aria-pressed',x===b?'true':'false')});
    var co=b.getAttribute('data-cotab');
    scope.querySelectorAll('[data-copanel]').forEach(function(p){
      p.hidden=p.getAttribute('data-copanel')!==co;});
    scope.querySelectorAll('.chart').forEach(function(el){
      if(!el.closest('[data-copanel]')||!el.closest('[data-copanel]').hidden)drawChart(el);});
  });
});
