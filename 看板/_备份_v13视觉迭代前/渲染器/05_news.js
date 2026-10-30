// 05_news.js —— 渲染器：资讯/公告feed（data-news 锚点 ← DDATA._news）
(function(){
  var KEY,ITEMS;
  for(KEY in NEWS){
    ITEMS=NEWS[KEY];
    if(!ITEMS||!ITEMS.length)continue;
    root.querySelectorAll('[data-news]').forEach(function(el){
      if(el.getAttribute('data-news')!==KEY)return;
      var ul=el.querySelector('ul.feed');if(!ul)return;
      ul.innerHTML=ITEMS.map(function(it){
        var zh=it.title_zh&&it.title_zh!==it.title;
        var tt=zh?(' title="'+escH(it.title)+'"'):'';
        return '<li><a class="fi" href="'+escH(it.url||'#')+'" target="_blank" rel="noopener">'
          +'<i>'+escH(it.date||'')+'</i><span'+tt+'>'+escH(zh?it.title_zh:it.title)+'</span></a></li>';
      }).join('');
    });
  }
})();
// 空feed兜底提示：数据为空时如实显示（不编造条目）
root.querySelectorAll('[data-news]').forEach(function(el){
  var ul=el.querySelector('ul.feed');
  if(ul&&!ul.querySelector('li')){
    ul.innerHTML='<li><a class="fi"><i>--</i><span>近7天暂无新稿 · 采集器每次运行自动更新</span></a></li>';
  }
});
