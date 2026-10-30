// 35_bind.js —— 渲染器：数值绑定（.val卡片 / .sc指标条 / ticker / statline）
function applyBind(pid, el, valEl, subEl){
  var s=getSeries(pid);if(!s)return;
  var b=BIND[pid]||[null,null];
  var last=s.rows[s.rows.length-1],v=last[1];
  if(valEl)valEl.innerHTML='<span class="vnum">'+fmtN(v,b[1])+'</span>'+(b[0]?'<span class="unit">'+b[0]+'</span>':'');
  if(subEl&&s.rows.length>1){
    var pv=s.rows[s.rows.length-2][1];
    var d=Math.round((v-pv)*Math.pow(10,(b[1]||0)))/Math.pow(10,(b[1]||0));
    var dir=d>=0?'up':'down',arw=d>=0?'▲':'▼';
    var pill='<span class="dpill '+dir+'">'+arw+' '+(d>=0?'+':'')+d+'</span>';
    subEl.insertAdjacentHTML('afterbegin',pill+' ');
  }
}
root.querySelectorAll('[data-k]').forEach(function(el){
  var ids=el.getAttribute('data-k').split(' ');var pid='P'+ids[0];
  if(!DDATA[pid])return;
  var valEl=el.querySelector('.val'),subEl=el.querySelector('.sub');
  if(valEl&&BIND[pid])applyBind(pid,el,valEl,subEl);
  if(el.classList.contains('sc')&&BIND[pid]){
    var s=getSeries(pid);if(s){var b=BIND[pid]||[null,null];
      var vEl=el.querySelector('.v');
      if(vEl)vEl.innerHTML='<span class="vnum">'+fmtN(s.rows[s.rows.length-1][1],b[1])+'</span>'+(b[0]?'<small>'+b[0]+'</small>':'');
      var sEl=el.querySelector('.s');
      if(sEl&&!sEl.textContent.includes('·'))sEl.textContent=s.rows[s.rows.length-1][0]+' · '+sEl.textContent;}
  }
});
root.querySelectorAll('[data-tk]').forEach(function(el){
  var pid=el.getAttribute('data-tk');var s=getSeries(pid);if(!s)return;
  var b=BIND[pid]||[null,null];var v=s.rows[s.rows.length-1][1];
  var vEl=el.querySelector('.v');
  if(vEl){
    if(b[0]==='%'){var sign=v>=0?'+':'';vEl.textContent=sign+fmtN(v,b[1])+'%';
      vEl.style.color=v>=0?'var(--up)':'var(--down)';}
    else vEl.innerHTML='<span class="vnum">'+fmtN(v,b[1])+'</span>'+(b[0]?'<small>'+b[0]+'</small>':'');
  }
});
root.querySelectorAll('[data-vk]').forEach(function(el){
  var pid=el.getAttribute('data-vk');var s=getSeries(pid);if(!s)return;
  var b=BIND[pid]||[null,null];var v=s.rows[s.rows.length-1][1];
  var bEl=el.querySelector('b');if(bEl)bEl.textContent=(v>=0?'':'')+fmtN(v,b[1])+((b[0]==='%')?'%':'');
});
