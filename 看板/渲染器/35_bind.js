// 35_bind.js —— 渲染器：数值绑定（.val卡片 / .sc指标条 / ticker / statline）
// v14：大数字滚动动画（REDUCE降级）、涨跌chip格式化（▲▼+绝对值，红涨绿跌）、.sc 较前值chip
var V8RBIND=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
function v8count(el,to,dec){
  if(V8RBIND){el.textContent=fmtN(to,dec);return}
  var from=to*0.72,t0=null;
  function step(t){if(!t0)t0=t;var p=Math.min(1,(t-t0)/520);p=1-Math.pow(1-p,3);
    el.textContent=fmtN(from+(to-from)*p,dec);
    if(p<1)requestAnimationFrame(step)}
  requestAnimationFrame(step);
}
function v8dec(b){return (b[1]==null)?2:b[1]}
function applyBind(pid, el, valEl, subEl){
  var s=getSeries(pid);if(!s)return;
  var b=BIND[pid]||[null,null];
  var last=s.rows[s.rows.length-1],v=last[1];
  if(valEl){
    valEl.innerHTML='<span class="vnum"></span>'+(b[0]?'<span class="unit">'+b[0]+'</span>':'');
    var vn=valEl.querySelector('.vnum');
    if(vn)v8count(vn,v,v8dec(b));
  }
  if(subEl&&s.rows.length>1){
    var pv=s.rows[s.rows.length-2][1];
    var d=Math.round((v-pv)*Math.pow(10,v8dec(b)))/Math.pow(10,v8dec(b));
    var dir=d>=0?'up':'down',arw=d>=0?'▲':'▼';
    var pill='<span class="dpill '+dir+'">'+arw+' '+(d>=0?'+':'')+Math.abs(d).toFixed(v8dec(b))+'</span>';
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
      if(sEl&&!sEl.textContent.includes('·'))sEl.textContent=s.rows[s.rows.length-1][0]+' · '+sEl.textContent;
      /* v14：较前值chip */
      if(vEl&&s.rows.length>1){
        var pv=s.rows[s.rows.length-2][1];
        var dd=Math.round((s.rows[s.rows.length-1][1]-pv)*Math.pow(10,v8dec(b)))/Math.pow(10,v8dec(b));
        var chg=document.createElement('span');
        chg.className='chg '+(dd>=0?'up':'down');
        chg.textContent=(dd>=0?'▲+':'▼')+Math.abs(dd).toFixed(v8dec(b));
        vEl.appendChild(chg);
      }
    }
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
/* v14.1修复：静态日期占位统一刷新。
   背景：骨架ticker日期行、卡JSON指标行标签/指标条说明/环形文案中的日期是构建期占位，
   此前绑定器只刷新数值导致"数值新、日期旧"。此块按各自数据最新一行的日期同步，
   只替换已存在的日期token（前缀日期·来源 / 最新MM-DD /（MM-DD）/（M月）），不动来源等其余文本。 */
(function(){
  function pidOf(host){
    if(!host)return null;
    var p=host.getAttribute('data-tk')||host.getAttribute('data-vk')||host.getAttribute('data-ring');
    if(!p){var dk=host.getAttribute('data-k');p=dk?('P'+String(dk).trim().split(/\s+/)[0].replace(/^P/,'')):null;}
    return p;
  }
  function fresh(el){
    var s=getSeries(pidOf(el.closest('[data-tk],[data-vk],[data-k],[data-ring]')));
    if(!s||!s.rows||!s.rows.length)return;
    var last=String(s.rows[s.rows.length-1][0]);
    if(!/^\d{4}-\d{2}-\d{2}$/.test(last))return;
    var md=last.slice(5,10),mo=Number(last.slice(5,7))+'月',t=el.textContent;
    var out=t.replace(/(^|\s)(\d{1,2}-\d{1,2})(期)?(\s*·)/,'$1'+md+'$3$4')
             .replace(/最新(\d{1,2}-\d{1,2})/,'最新'+md)
             .replace(/（(\d{1,2}-\d{1,2})）/,'（'+md+'）')
             .replace(/（(\d{1,2})月）/,'（'+mo+'）')
             .replace(/(^|\s)(\d{1,2})月(\s*·)/,'$1'+mo+'$3');
    if(out!==t)el.textContent=out;
  }
  root.querySelectorAll('.tk>.s,.sc>.s,.statline>.k,.rs').forEach(fresh);
})();
