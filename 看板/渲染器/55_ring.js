// 55_ring.js —— 渲染器：Qi2环形图（[data-ring]：col1=Qi2数 col2=全库总数 col3=Qi2.2(25W)数）
// v14：圆弧生长动画 + 占比滚动（REDUCE降级为直出）；结构色定妆品牌蓝
// v19.1：双环对比——存在第二组 .rf/.rt 时，col3(Qi2.2)/全库 画第二环（琥珀色，类 ralt）
(function(){
  var REDUCE=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  root.querySelectorAll('[data-ring]').forEach(function(el){
    var d=DDATA[el.getAttribute('data-ring')];
    if(!d||!d.rows||!d.rows.length||d.cols.length<2)return;
    var last=d.rows[d.rows.length-1],qi2=last[1],tot=last[2],qi22=last[3];
    if(qi2==null||!tot)return;
    var pct=Math.round(qi2/tot*100),C=188.5;
    var pcts=[pct];
    if(qi22!=null&&el.querySelector('.rf.ralt'))pcts.push(Math.round(qi22/tot*100));   // v19.1：第二环=Qi2.2占全库
    var rfs=el.querySelectorAll('.rf'),rts=el.querySelectorAll('.rt');
    for(var i=0;i<rfs.length&&i<pcts.length;i++){
      (function(rf,p){
        if(REDUCE){rf.setAttribute('stroke-dasharray',(C*p/100).toFixed(1)+' '+C);}
        else{
          rf.setAttribute('stroke-dasharray','0 '+C);
          setTimeout(function(){rf.setAttribute('stroke-dasharray',(C*p/100).toFixed(1)+' '+C)},60);
        }
      })(rfs[i],pcts[i]);
    }
    for(var j=0;j<rts.length&&j<pcts.length;j++){
      (function(rt,p){
        if(REDUCE){rt.textContent=p+'%';}
        else{var t0=null;
          function step(t){if(!t0)t0=t;var q=Math.min(1,(t-t0)/900);
            rt.textContent=Math.round(p*(1-Math.pow(1-q,3)))+'%';
            if(q<1)requestAnimationFrame(step)}
          requestAnimationFrame(step);
        }
      })(rts[j],pcts[j]);
    }
    var rv=el.querySelector('.rv');if(rv)rv.textContent=fmtN(qi2,0)+' / '+fmtN(tot,0)+' 条';
    var sub='Qi2（MPP）认证累计 · 最新'+String(last[0]).slice(5)+' · 每周增长';
    if(qi22!=null)sub+=' · 其中Qi2.2(25W) '+fmtN(qi22,0)+'条';   // v19：Qi2.2认证数(25W)列
    var rs=el.querySelector('.rs');if(rs)rs.textContent=sub;
  });
})();
