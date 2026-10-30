// 55_ring.js —— 渲染器：Qi2环形图（[data-ring]：col1=Qi2数 col2=全库总数）
root.querySelectorAll('[data-ring]').forEach(function(el){
  var d=DDATA[el.getAttribute('data-ring')];
  if(!d||!d.rows||!d.rows.length||d.cols.length<2)return;
  var last=d.rows[d.rows.length-1],qi2=last[1],tot=last[2];
  if(qi2==null||!tot)return;
  var pct=Math.round(qi2/tot*100),C=188.5;
  var rf=el.querySelector('.rf');if(rf)rf.setAttribute('stroke-dasharray',(C*pct/100).toFixed(1)+' '+C);
  var rt=el.querySelector('.rt');if(rt)rt.textContent=pct+'%';
  var rv=el.querySelector('.rv');if(rv)rv.textContent=fmtN(qi2,0)+' / '+fmtN(tot,0)+' 条';
  var rs=el.querySelector('.rs');if(rs)rs.textContent='Qi2（MPP）认证累计 · 最新'+String(last[0]).slice(5)+' · 每周增长';
});
