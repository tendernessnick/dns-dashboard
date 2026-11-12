// 60_toplist.js —— 主页仅展示已有TOPS的前5条；总样本数与可见条目数分开说明。
// TOPS.title/img在生成端已HTML转义，先解码一次，再用纯DOM属性/文本安全输出。
(function(){
  function decoded(value){var text=document.createElement('textarea');text.innerHTML=String(value==null?'':value);return text.value}
  function node(tag,cls,text){var el=document.createElement(tag);if(cls)el.className=cls;if(text!=null)el.textContent=String(text);return el}
  function remoteImage(value){
    var text=decoded(value).trim();if(!/^https?:\/\//i.test(text))return '';
    try{var url=new URL(text);return url.protocol==='http:'||url.protocol==='https:'?url.href:''}catch(_){return ''}
  }
  root.querySelectorAll('[data-toplist]').forEach(function(el){
    var tp=(typeof TOPS!=='undefined')&&TOPS[el.getAttribute('data-toplist')];
    if(!tp||!Array.isArray(tp.items)||!tp.items.length){
      var empty=node('li','top-empty','暂无可用榜单样本');el.replaceChildren(empty);return;
    }
    var fragment=document.createDocumentFragment();
    tp.items.slice(0,5).forEach(function(it){
      if(!it||typeof it!=='object')return;
      var rank=typeof it.rank==='number'&&Number.isFinite(it.rank)&&it.rank>0?it.rank:null;
      var asin=String(it.asin||''),validAsin=/^[A-Z0-9]{10}$/i.test(asin);
      var row=node('li','top-product'),link=node(validAsin?'a':'div','fi');
      if(validAsin){link.href='https://www.amazon.com/dp/'+encodeURIComponent(asin);link.target='_blank';link.rel='noopener noreferrer'}
      link.appendChild(node('i','rk'+(rank!=null&&rank<=3?' r'+rank:''),rank==null?'—':rank));
      var title=decoded(it.title),img=remoteImage(it.img);
      if(img){
        var image=node('img','lthumb');image.src=img;image.alt='';image.loading='lazy';image.decoding='async';
        image.addEventListener('error',function(){image.remove()},{once:true});link.appendChild(image);
      }
      var info=node('span','top-product-info'),name=node('span','top-product-title',title||'商品标题未提供');
      name.title=title;info.appendChild(name);
      var meta=node('span','top-product-meta');
      if(typeof it.price==='number'&&Number.isFinite(it.price)&&it.price>=0){
        meta.appendChild(node('i','ptag','$'+it.price));
      }else meta.appendChild(node('span','top-price-missing','价格未提供'));
      if(/anker/i.test(title))meta.appendChild(node('i','ankertag','ANKER'));
      if(validAsin)meta.appendChild(node('span','top-product-link','商品页 ↗'));
      info.appendChild(meta);link.appendChild(info);row.appendChild(link);fragment.appendChild(row);
    });
    el.replaceChildren(fragment);
  });
  root.querySelectorAll('[data-topsub]').forEach(function(el){
    var tp=(typeof TOPS!=='undefined')&&TOPS[el.getAttribute('data-topsub')];
    if(!tp)return;
    var shown=Array.isArray(tp.items)?tp.items.slice(0,5).filter(function(it){return it&&typeof it==='object'}).length:0;
    var count=typeof tp.total==='number'&&Number.isFinite(tp.total)&&tp.total>=0?String(tp.total):'未提供';
    var text='展示 '+shown+' 条 · 本次榜单样本 '+count+' 条';
    if(typeof tp.anker==='number'&&Number.isFinite(tp.anker))text+=' · Anker入榜 '+tp.anker+' 席';
    if(typeof tp.avg==='number'&&Number.isFinite(tp.avg)&&tp.avg>=0)text+=' · 样本均价 $'+tp.avg;
    text+=' · 快照 '+String(tp.date||'日期未提供')+' · '+String(el.getAttribute('data-top-label')||tp.label||'');
    el.textContent=text;
  });
})();
