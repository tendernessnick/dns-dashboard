// 60_toplist.js —— 渲染器：Amazon榜单快照（[data-toplist] TOP5图文 + [data-topsub]统计行）
// v14：名次徽章（金银铜）、价格chip、Anker行高亮
root.querySelectorAll('[data-toplist]').forEach(function(el){
  var tp=(typeof TOPS!=='undefined')&&TOPS[el.getAttribute('data-toplist')];
  if(!tp||!tp.items||!tp.items.length)return;
  el.innerHTML=tp.items.map(function(it){
    var rk=it.rank<=3?('rk r'+it.rank):'rk';
    var ak=/anker/i.test(it.title||'')?'<i class="ankertag">ANKER</i>':'';
    var pr=it.price!=null?'<i class="ptag">$'+it.price+'</i>':'';
    var u=it.asin?('https://www.amazon.com/dp/'+it.asin):'https://www.amazon.com/Best-Sellers-Cell-Phones-Accessories/zgbs/wireless';
    var im=it.img?('<img class="lthumb" loading="lazy" src="'+escH(it.img)+'" alt="">'):'';
    return '<li><a class="fi" href="'+u+'" target="_blank" rel="noopener">'
      +'<i class="'+rk+'">'+it.rank+'</i>'+im+'<span>'+it.title+'</span>'+pr+ak+'</a></li>';
  }).join('');
});
root.querySelectorAll('[data-topsub]').forEach(function(el){
  var tp=(typeof TOPS!=='undefined')&&TOPS[el.getAttribute('data-topsub')];
  if(!tp)return;
  el.textContent='TOP'+tp.total+' · Anker '+tp.anker+'席'+(tp.avg?(' · 均价$'+tp.avg):'')+' · 快照'+tp.date+' · '+tp.label;
});
