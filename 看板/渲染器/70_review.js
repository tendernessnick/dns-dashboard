// 70_review.js —— 渲染器：图文拆解卡（data-review 锚点 ← REVIEWS，v18）
// P91我爱音频网·拆解；卡样移植 模块样板_耳机评测.html v8（缩略图+chips+两行摘要+整卡超链接），
// 配色改用看板主题变量；数据由 生成数据.py 从 RPA数据/*/*/_meta.json 生成。
(function(){
  if(typeof REVIEWS==='undefined')return;
  root.querySelectorAll('[data-review]').forEach(function(el){
    var pid='P'+el.getAttribute('data-review');
    var d=REVIEWS[pid];
    if(!d||!d.items||!d.items.length){
      el.innerHTML='<div class="rev-empty">暂无图文数据 · 采集器每日自动更新（低频主题近期可能无新稿）</div>';
      return;
    }
    el.innerHTML=d.items.map(function(it){
      var chips=(it.chips||[]).map(function(c,i){
        return '<span class="rchip'+(i===0?' hot':'')+'">'+escH(c)+'</span>';
      }).join('');
      var img=it.img
        ?'<img class="rthumb" src="'+it.img+'" alt="'+escH(it.name)+'" loading="lazy">'
        :'<span class="rthumb rnoimg">'+escH(d.noimg||'图')+'</span>';
      return '<a class="revcard" href="'+escH(it.url||'#')+'" target="_blank" rel="noopener">'
        +img
        +'<span class="rinfo"><span class="rl1"><span class="rname">'+escH(it.name)+'</span>'
        +(it.tag?('<span class="rtag">'+escH(it.tag)+'</span>'):'')
        +'<span class="rdate">'+escH(it.date||'')+'</span></span>'
        +(chips?('<span class="rchips">'+chips+'</span>'):'')
        +(it.desc?('<span class="rdesc">'+escH(it.desc)+'</span>'):'')
        +'</span></a>';
    }).join('');
  });
})();
