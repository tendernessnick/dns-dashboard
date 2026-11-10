// 17_spark.js —— 渲染器：KPI卡迷你走势（v14新增）
// 规则：.card.kpi 无 .chart、无多品类/多行清单、且 data-k 首个P号序列≥2点时，
// 自动在 .foot 前注入 sparkline（趋势涨跌着色 + 淡面积 + 尾点），免卡配置
// v19.1：悬停查值——导引线+悬浮点+.ctool数值提示（日期 · 值 单位 · 较前期变化），
// 与15_chart同款交互；svg为preserveAspectRatio=none非等比拉伸，故导引/悬浮点用
// 绝对定位div（像素空间）而非svg元素防变形；ResizeObserver重绘只重建图形，监听一次性绑定
(function(){
  var REDUCE=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var W=200,H=36,P=3;   // viewBox常量（绘制与命中换算共用）
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
    var pid=el.getAttribute('data-v8spark');
    var s=getSeries(pid);if(!s||s.rows.length<2)return;
    var n=s.rows.length;
    var vals=s.rows.map(function(r){return r[1]});
    var mn=Math.min.apply(null,vals),mx=Math.max.apply(null,vals);
    var rg=(mx-mn)||Math.abs(mx)*0.02||1;
    function X(i){return P+i*(W-2*P)/(n-1)}
    function Y(v){return P+(1-(v-mn)/rg)*(H-2*P)}
    var cs=getComputedStyle(root);
    var c=vals[n-1]>=vals[0]?((cs.getPropertyValue('--up')||'#B42318').trim()):((cs.getPropertyValue('--down')||'#0E7A54').trim());
    var pts=vals.map(function(v,i){return X(i).toFixed(1)+','+Y(v).toFixed(1)}).join(' ');
    el.innerHTML='<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" aria-hidden="true">'
      +'<polygon fill="'+c+'" opacity=".12" points="'+P+','+(H-P)+' '+pts+' '+(W-P)+','+(H-P)+'"/>'
      +'<polyline fill="none" stroke="'+c+'" stroke-width="1.8" vector-effect="non-scaling-stroke" stroke-linejoin="round" points="'+pts+'"/>'
      +'<circle cx="'+X(n-1).toFixed(1)+'" cy="'+Y(vals[n-1]).toFixed(1)+'" r="2.4" fill="'+c+'"/></svg>'
      +'<div class="sguide"></div><div class="sdot"></div>';
    if(!el.querySelector('.ctool')){
      var tip=document.createElement('div');tip.className='ctool';el.appendChild(tip);
    }
  }
  root.querySelectorAll('[data-v8spark]').forEach(function(el){
    spark(el);
    if(el._sparkBound)return;el._sparkBound=1;
    function hide(){var g=el.querySelector('.sguide'),d=el.querySelector('.sdot'),t=el.querySelector('.ctool');
      if(g)g.style.display='none';if(d)d.style.display='none';if(t)t.style.display='none';}
    el.addEventListener('pointermove',function(e){
      var pid=el.getAttribute('data-v8spark');
      var s=getSeries(pid);if(!s||s.rows.length<2)return;
      var n=s.rows.length,vals=s.rows.map(function(r){return r[1]});
      var mn=Math.min.apply(null,vals),mx=Math.max.apply(null,vals);
      var rg=(mx-mn)||Math.abs(mx)*0.02||1;
      var r=el.getBoundingClientRect();
      var px=(e.clientX-r.left)/r.width*W;
      var i=Math.round((px-P)/(W-2*P)*(n-1));i=Math.max(0,Math.min(n-1,i));
      var v=vals[i],gl=el.querySelector('.sguide'),dt=el.querySelector('.sdot'),tip=el.querySelector('.ctool');
      if(!gl||!dt||!tip)return;
      if(v==null){hide();return}
      var lx=(P+i*(W-2*P)/(n-1))/W*r.width, ly=(P+(1-(v-mn)/rg)*(H-2*P))/H*r.height;
      var cs=getComputedStyle(root);
      var c=vals[n-1]>=vals[0]?((cs.getPropertyValue('--up')||'#B42318').trim()):((cs.getPropertyValue('--down')||'#0E7A54').trim());
      gl.style.left=lx+'px';gl.style.display='block';
      dt.style.left=lx+'px';dt.style.top=ly+'px';dt.style.borderColor=c;dt.style.display='block';
      var b=BIND[pid]||[null,null],dec=(b[1]==null)?2:b[1],unit=b[0]||'';
      var dd='';if(i>0&&vals[i-1]!=null){
        var d0=Math.round((v-vals[i-1])*Math.pow(10,dec))/Math.pow(10,dec);
        dd='<span class="d '+(d0>=0?'up':'down')+'">（较前期 '+(d0>=0?'+':'')+d0+'）</span>';}
      tip.innerHTML=escH(s.rows[i][0])+' · <b>'+fmtN(v,dec)+'</b> '+escH(unit)+dd;
      tip.style.display='block';
      var tx=lx+10;if(tx+tip.offsetWidth>r.width+8)tx=lx-tip.offsetWidth-10;
      tip.style.left=tx+'px';
      var ty=ly-tip.offsetHeight-8;
      if(ty<0)ty=ly+12;
      tip.style.top=ty+'px';
    });
    el.addEventListener('pointerleave',hide);
    el.addEventListener('pointercancel',hide);
    el.addEventListener('pointerup',function(e){if(e.pointerType!=='mouse')hide()});
  });
  if(!REDUCE&&'ResizeObserver' in window){
    var ro=new ResizeObserver(function(es){es.forEach(function(e){if(e.target.classList.contains('spark'))spark(e.target)})});
    root.querySelectorAll('[data-v8spark]').forEach(function(el){ro.observe(el)});
  }
})();
