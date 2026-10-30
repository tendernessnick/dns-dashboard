// 60_toplist.js —— 渲染器：Amazon榜单快照（[data-toplist] TOP5图文 + [data-topsub]统计行）
root.querySelectorAll('[data-toplist]').forEach(function(el){
  var tp=(typeof TOPS!=='undefined')&&TOPS[el.getAttribute('data-toplist')];
  if(!tp||!tp.items||!tp.items.length)return;
  el.innerHTML=tp.items.map(function(it){
    var pr=it.price!=null?(' · $'+it.price):'';
    var u=it.asin?('https://www.amazon.com/dp/'+it.asin):'https://www.amazon.com/Best-Sellers-Cell-Phones-Accessories/zgbs/wireless';
    var im=it.img?('<img class="lthumb" loading="lazy" src="'+escH(it.img)+'" alt="">'):'';
    return '<li><a class="fi" href="'+u+'" target="_blank" rel="noopener">'+im+'<i>#'+it.rank+'</i><span>'+it.title+pr+'</span></a></li>';
  }).join('');
});
root.querySelectorAll('[data-topsub]').forEach(function(el){
  var tp=(typeof TOPS!=='undefined')&&TOPS[el.getAttribute('data-topsub')];
  if(!tp)return;
  el.textContent='TOP'+tp.total+' · Anker '+tp.anker+'席'+(tp.avg?(' · 均价$'+tp.avg):'')+' · 快照'+tp.date+' · '+tp.label;
});
