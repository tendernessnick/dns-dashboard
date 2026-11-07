// 72_calendar.js —— 渲染器：议息日历动态覆盖（data-cal 锚点 ← CAL，v18.6）
// P16美联储 / P20欧洲央行：collect_P16_议息日历.py 解析官网日历与决议数据 → 议息日历.json → data.js。
// CAL 有值时覆盖模块JSON静态快照（时间线 + 说明行）；无数据时保留静态兜底不动。
// 锚点约定：data-cal / data-cal-desc 存数字P号（Pn剥P），CAL 键带 P 前缀——两处键勿混用。
(function(){
  if(typeof CAL==='undefined')return;
  root.querySelectorAll('[data-cal]').forEach(function(el){
    var id=el.getAttribute('data-cal');      // 锚点存数字P号(Pn剥P)
    var p='P'+id;                            // CAL键带P前缀
    var d=CAL[p];
    if(!d||!d.时间线||!d.时间线.length)return;
    el.innerHTML=d.时间线.map(function(it){
      var cls=it.下一个?' class="next"':'';
      return '<li'+cls+'><b>'+escH(it.日期)+'</b>'+escH(it.文本||'')+'</li>';
    }).join('');
    var desc=document.querySelector('[data-cal-desc="'+id+'"]');  // desc锚点与data-cal同用数字P号
    if(desc&&d.说明)desc.textContent=d.说明;
  });
})();
