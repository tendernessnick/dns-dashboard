// 17_spark.js —— 渲染器：KPI卡迷你走势（v14新增）
// 规则：.card.kpi 无 .chart、无多品类/多行清单、且 data-k 首个P号序列≥2点时，
// 自动在 .foot 前注入 sparkline（趋势涨跌着色 + 淡面积 + 尾点），免卡配置
(function(){
  var REDUCE=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  root.querySelectorAll('.card.kpi').forEach(function(card){
    if(card.querySelector('.chart'))return;
    if(card.querySelector('ul.multi,[data-multi],.sparkrow'))return;
    var dk=card.getAttribute('data-k');if(!dk)return;
    var pid='P'+dk.split(' ')[0];
    var s=getSeries(pid);if(!s||s.rows.length<3)return;// 少于3点无趋势意义，不注入
    var row=document.createElement('div');row.className='sparkrow';
    row.innerHTML='<div class="spark" data-v8spark="'+pid+'"></div>';
    var foot=card.querySelector('.foot');
    if(foot)card.insertBefore(row,foot);else card.appendChild(row);
  });
  function spark(el){
    var s=getSeries(el.getAttribute('data-v8spark'));if(!s||s.rows.length<2)return;
    var W=200,H=36,p=3,n=s.rows.length;
    var vals=s.rows.map(function(r){return r[1]});
    var mn=Math.min.apply(null,vals),mx=Math.max.apply(null,vals);
    var rg=(mx-mn)||Math.abs(mx)*0.02||1;
    function X(i){return p+i*(W-2*p)/(n-1)}
    function Y(v){return p+(1-(v-mn)/rg)*(H-2*p)}
    var cs=getComputedStyle(root);
    var c=vals[n-1]>=vals[0]?((cs.getPropertyValue('--up')||'#B42318').trim()):((cs.getPropertyValue('--down')||'#0E7A54').trim());
    var pts=vals.map(function(v,i){return X(i).toFixed(1)+','+Y(v).toFixed(1)}).join(' ');
    el.innerHTML='<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" aria-hidden="true">'
      +'<polygon fill="'+c+'" opacity=".12" points="'+p+','+(H-p)+' '+pts+' '+(W-p)+','+(H-p)+'"/>'
      +'<polyline fill="none" stroke="'+c+'" stroke-width="1.8" vector-effect="non-scaling-stroke" stroke-linejoin="round" points="'+pts+'"/>'
      +'<circle cx="'+X(n-1).toFixed(1)+'" cy="'+Y(vals[n-1]).toFixed(1)+'" r="2.4" fill="'+c+'"/></svg>';
  }
  root.querySelectorAll('[data-v8spark]').forEach(spark);
  if(!REDUCE&&'ResizeObserver' in window){
    var ro=new ResizeObserver(function(es){es.forEach(function(e){if(e.target.classList.contains('spark'))spark(e.target)})});
    root.querySelectorAll('[data-v8spark]').forEach(function(el){ro.observe(el)});
  }
})();
