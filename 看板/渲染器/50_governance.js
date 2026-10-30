// 50_governance.js —— 渲染器：数据治理标注（数据截至 / 可靠度角标 / 快报徽标 / 待补录）
// 数据来源：词条注册表（META/PEND/ASOF 由 data.js 下发）
(function(){
  if(ASOF){var el0=document.getElementById('asof');if(el0)el0.textContent=ASOF;}
  root.querySelectorAll('.card[data-k]').forEach(function(el){
    var pid='P'+el.getAttribute('data-k').split(' ')[0];
    var meta=META[pid]; if(!meta)return;
    var top=el.querySelector('.card-top'); if(!top)return;
    var rl=meta.r||'';
    var b=document.createElement('span');
    b.className='rlbadge '+(rl==='A'?'a':rl==='C'?'c':'b');
    b.textContent=rl;
    b.title='可靠度'+rl+'级'+(meta.k?('：'+meta.k):'')+'（数据治理分级）';
    top.appendChild(b);
    if(PEND[pid]){
      var w=document.createElement('span');w.className='warn-tag';
      w.textContent='缺'+PEND[pid]+'待考证';w.title='缺失季度待人工考证补录（见待补录清单）';
      top.appendChild(w);
    }else{
      var s=getSeries(pid,1);
      if(s&&/快报|闪估|ECFIN/.test(s.src||'')){
        var kb=document.createElement('span');kb.className='kbflag';kb.textContent='快报';
        kb.title='当前为快报/闪估值，正式值发布后自动替换';
        top.appendChild(kb);
      }
    }
  });
})();
