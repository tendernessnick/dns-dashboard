// 55_ring.js —— 渲染器：Qi2环形图（[data-ring]：col1=Qi2数 col2=全库总数）
// v14：圆弧生长动画 + 占比滚动（REDUCE降级为直出）；结构色定妆品牌蓝
(function(){
  var REDUCE=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  root.querySelectorAll('[data-ring]').forEach(function(el){
    var d=DDATA[el.getAttribute('data-ring')];
    if(!d||!d.rows||!d.rows.length||d.cols.length<2)return;
    var last=d.rows[d.rows.length-1],qi2=last[1],tot=last[2];
    if(qi2==null||!tot)return;
    var pct=Math.round(qi2/tot*100),C=188.5;
    var rf=el.querySelector('.rf');
    if(rf){
      if(REDUCE){rf.setAttribute('stroke-dasharray',(C*pct/100).toFixed(1)+' '+C);}
      else{
        rf.setAttribute('stroke-dasharray','0 '+C);
        setTimeout(function(){rf.setAttribute('stroke-dasharray',(C*pct/100).toFixed(1)+' '+C)},60);
      }
    }
    var rt=el.querySelector('.rt');
    if(rt){
      if(REDUCE){rt.textContent=pct+'%';}
      else{var t0=null;
        function step(t){if(!t0)t0=t;var p=Math.min(1,(t-t0)/900);
          rt.textContent=Math.round(pct*(1-Math.pow(1-p,3)))+'%';
          if(p<1)requestAnimationFrame(step)}
        requestAnimationFrame(step);
      }
    }
    var rv=el.querySelector('.rv');if(rv)rv.textContent=fmtN(qi2,0)+' / '+fmtN(tot,0)+' 条';
    var rs=el.querySelector('.rs');if(rs)rs.textContent='Qi2（MPP）认证累计 · 最新'+String(last[0]).slice(5)+' · 每周增长';
  });
})();
