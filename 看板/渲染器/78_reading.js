// 精选入口只呈现已有观测和原文，不生成事件判断或新的数据源。
(function(){
  function startReading(){
    function node(tag,cls,text){
      var el=document.createElement(tag);if(cls)el.className=cls;
      if(text!=null)el.textContent=String(text);return el;
    }
    function imageUrl(value){
      var s=String(value||'');
      if(typeof MEDIA_OMISSIONS!=='undefined'&&MEDIA_OMISSIONS.indexOf(s)>=0)return '';
      if(/^data:image\/(?:png|jpe?g|webp|gif);base64,[a-z0-9+/=\s]+$/i.test(s))return s;
      if(/^(?:\.\/)?媒体\//.test(s)){
        try{var decoded=decodeURIComponent(s).replace(/\\/g,'/');
          if(!decoded.split('/').some(function(p){return p==='..'})&&!/[\x00-\x1f]/.test(decoded))return s;
        }catch(e){}return '';
      }
      try{var u=new URL(s);return /^https?:$/.test(u.protocol)?u.href:''}catch(e){return ''}
    }
    root.querySelectorAll('[data-focus-kind]').forEach(function(box){
      var kind=box.dataset.focusKind,pid=box.dataset.focusPid,body=box.querySelector('.focus-content');
      var card=Array.from(root.querySelectorAll('[data-mid]')).find(function(c){return c.dataset.mid===box.dataset.focusModule});
      if(!body||!card)return;
      if(kind==='series'){
        var data=DDATA[pid],rows=data&&data.rows?data.rows.filter(function(r){return r[1]!=null}):[];
        if(!rows.length){body.appendChild(node('p','focus-empty','暂无有效观测'));return}
        var last=rows[rows.length-1],bind=BIND[pid]||['',2];
        var val=node('p','focus-value',(bind[0]==='%'&&Number(last[1])>0?'+':'')+fmtN(Number(last[1]),bind[1]));
        val.appendChild(node('span','focus-unit',bind[0]||''));body.appendChild(val);
        body.appendChild(node('p','focus-date','观测日期 '+last[0]));
        var chart=node('div','chart focus-chart');chart.setAttribute('data-chart',pid);
        if(card.getAttribute('data-change')==='none')chart.setAttribute('data-change','none');
        if(card.getAttribute('data-trend')!=='none'&&rows.length>1){
          body.appendChild(chart);drawChart(chart,true);charts.push(chart);
        }
        var action=box.querySelector('button');action.textContent='查看完整趋势 ↗';
        action.setAttribute('data-detail-pid',pid);action.removeAttribute('data-detail-module');
      }else if(kind==='review'){
        var reviews=typeof REVIEWS!=='undefined'&&REVIEWS[pid],saved=reviews&&reviews.items||[];
        var item=saved.find(function(it){return imageUrl(it.img)&&it.desc})||saved.find(function(it){return imageUrl(it.img)})||saved[0];
        if(!item){body.appendChild(node('p','focus-empty','当前没有可展示的图文'));return}
        var src=imageUrl(item.img);
        if(src){var img=node('img','focus-image');img.src=src;img.alt=item.name||'产品图片';img.loading='lazy';body.appendChild(img)}
        else body.appendChild(node('div','focus-image-placeholder','图片待核对'));
        body.appendChild(node('h3','focus-story',item.name));
        body.appendChild(node('p','focus-date',item.date||'发布日期未提供'));
        box.querySelector('button').textContent='查看图文 ↗';
        box.querySelector('button').setAttribute('data-detail-review',pid);
        box.querySelector('button').setAttribute('data-detail-index',String(saved.indexOf(item)));
        box.querySelector('button').removeAttribute('data-detail-module');
      }else if(kind==='top'){
        var top=typeof TOPS!=='undefined'&&TOPS[pid],items=top&&top.items||[];
        if(!items.length){body.appendChild(node('p','focus-empty','当前没有榜单样本'));return}
        var list=node('ol','focus-toplist');
        items.slice(0,3).forEach(function(it){var li=node('li');li.appendChild(node('span','focus-rank',it.rank));
          var entities={'&amp;':'&','&lt;':'<','&gt;':'>','&quot;':'"','&#39;':"'"};
          var title=String(it.title||'').replace(/&(?:amp|lt|gt|quot);|&#39;/g,function(v){return entities[v]});
          li.appendChild(node('span','focus-product',title));li.appendChild(node('b','focus-price',it.price==null?'价格未提供':'$'+it.price));list.appendChild(li)});
        body.appendChild(list);body.appendChild(node('p','focus-date','样本日期 '+(top.date||'未提供')));
        box.querySelector('button').textContent='查看榜单样本 ↗';
      }else{
        var feed=card.querySelector('.feed li .fi span');
        var desc=card.querySelector('.desc');
        body.appendChild(node('p','focus-module-text',feed?feed.textContent:desc?desc.textContent:'查看现有说明与来源入口'));
        var status=card.querySelector('.chip');if(status)body.appendChild(node('p','focus-date',status.textContent));
      }
    });
    // 自然阅读顺序：规划位置放在末尾，单张规划卡原位展开。
    root.querySelectorAll('.plan-details summary').forEach(function(s){s.textContent='查看建设规划'});
    var large=document.getElementById('readingSize');
    if(large)large.addEventListener('click',function(){
      var on=root.classList.toggle('large-reading');large.setAttribute('aria-pressed',String(on));
      large.textContent=on?'标准字号':'放大阅读';
      charts.forEach(function(el){if(el.clientWidth)drawChart(el,true)});
      shareEls.forEach(function(el){if(el.clientWidth)drawShare(el)});
    });
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',startReading,{once:true});else startReading();
})();
