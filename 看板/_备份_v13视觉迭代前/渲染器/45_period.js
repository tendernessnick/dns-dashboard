// 45_period.js —— 渲染器：全局周期选择器（.pctl，切换后重绘所有可见折线图）
var pbtns=[].slice.call(root.querySelectorAll('.pctl b'));
pbtns.forEach(function(b){
  b.addEventListener('click',function(){
    pbtns.forEach(function(x){x.classList.toggle('on',x===b)});
    PSEL=b.hasAttribute('data-all')?'all':{months:parseInt(b.getAttribute('data-m'),10)};
    root.querySelectorAll('.chart').forEach(function(el){
      var p=el.closest('[data-copanel]');
      if(!p||!p.hidden)drawChart(el);});
  });
});
