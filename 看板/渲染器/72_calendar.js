// 72_calendar.js —— 渲染器：议息日历动态覆盖（data-cal 锚点 ← CAL，v18.6）
// P16美联储 / P20欧洲央行：collect_P16_议息日历.py 解析官网日历与决议数据 → 议息日历.json → data.js。
// CAL 有值时覆盖模块JSON静态快照（时间线 + 说明行）；无数据时保留静态兜底不动。
// 锚点约定（v18.9统一）：data-cal 与 data-cal-desc 都存完整P号（如"P16"），与 CAL 键同名——
// v18.6的两套键（锚点存数字/CAL带P前缀）曾致静默失败，现一处同名处处同名。
(function(){
  if(typeof CAL==='undefined')return;
  root.querySelectorAll('[data-cal]').forEach(function(el){
    var pid=el.getAttribute('data-cal');     // 完整P号，即CAL键
    var d=CAL[pid];
    if(!d||!d.时间线||!d.时间线.length)return;
    el.innerHTML=d.时间线.map(function(it){
      var cls=it.下一个?' class="next"':'';
      return '<li'+cls+'><b>'+escH(it.日期)+'</b>'+escH(it.文本||'')+'</li>';
    }).join('');
    var card=el.closest('.card');   // desc在所在卡内找（多面板同号不漏刷）
    var desc=card&&card.querySelector('[data-cal-desc="'+pid+'"]');
    if(desc&&d.说明)desc.textContent=d.说明;
  });
})();
