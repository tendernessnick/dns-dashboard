// 图文资讯整卡打开原文，左右按钮切页；图片、摘要及标签均来自已有REVIEWS。
(function(){
  if(typeof REVIEWS==='undefined')return;
  function webURL(value){
    var text=String(value||'').trim();if(!/^https?:\/\//i.test(text))return '';
    try{var url=new URL(text);return url.protocol==='http:'||url.protocol==='https:'?url.href:''}catch(_){return ''}
  }
  function imageURL(value){
    var text=String(value||'').trim();
    if(typeof MEDIA_OMISSIONS!=='undefined'&&MEDIA_OMISSIONS.indexOf(text)>=0)return '';
    var remote=webURL(text);if(remote)return remote;
    if(/^data:image\/(?:jpeg|png|gif|webp|avif|bmp);base64,[a-z0-9+/=\s]+$/i.test(text))return text;
    if(!/^(?:\.\/)?媒体\/P\d+\//.test(text)||/[\\\u0000-\u001f]/.test(text))return '';
    text=text.replace(/^\.\//,'');
    var unsafe=text.split('/').some(function(part){
      try{part=decodeURIComponent(part)}catch(_){}
      return part==='..'||part==='.'||/[\\/]/.test(part);
    });
    return unsafe?'':text;
  }
  function node(tag,cls,text){
    var el=document.createElement(tag);if(cls)el.className=cls;
    if(text!=null)el.textContent=String(text);return el;
  }
  root.querySelectorAll('[data-review]').forEach(function(el){
    var pid=String(el.getAttribute('data-review')||'');if(!/^P/i.test(pid))pid='P'+pid;
    pid=pid.replace(/^p/,'P');
    var d=REVIEWS[pid];
    if(!d||!Array.isArray(d.items)||!d.items.length){
      el.replaceChildren(node('div','rev-empty','暂无图文数据 · 低频主题近期可能无新稿'));
      return;
    }
    var fragment=document.createDocumentFragment();
    d.items.forEach(function(it,index){
      if(!it||typeof it!=='object')return;
      var url=webURL(it.url);
      var card=node(url?'a':'article','revcard story-link'),media=node('div','rmedia'),info=node('div','rinfo');
      var name=String(it.name||'未命名图文'),src=imageURL(it.img);
      card.setAttribute('data-article-pid',pid);card.setAttribute('data-article-index',String(index));
      if(url){card.href=url;card.target='_blank';card.rel='noopener noreferrer';card.setAttribute('aria-label','打开原文：'+name)}
      function placeholder(){media.replaceChildren(node('span','rthumb rnoimg',it.img?'图片待核对':d.noimg||'暂无配图'))}
      if(src){
        var img=node('img','rthumb');img.src=src;img.alt=name;img.loading='lazy';img.decoding='async';
        img.addEventListener('error',placeholder,{once:true});media.appendChild(img);
      }else placeholder();
      var title=node('h4','rname',name);title.title=name;
      // 完整标题保留在DOM与title中，卡片中按可用空间排版。
      title.style.whiteSpace='normal';title.style.display='-webkit-box';
      title.style.webkitLineClamp='2';title.style.webkitBoxOrient='vertical';title.style.overflow='hidden';
      info.appendChild(title);
      var meta=node('div','rmeta');
      if(it.tag)meta.appendChild(node('span','rtag',it.tag));
      if(it.date)meta.appendChild(node('span','rdate',it.date));
      if(meta.childNodes.length)info.appendChild(meta);
      if(Array.isArray(it.chips)&&it.chips.length){
        var chips=node('div','rchips');it.chips.slice(0,6).forEach(function(chip,i){
          chips.appendChild(node('span','rchip'+(i===0?' hot':''),chip));
        });info.appendChild(chips);
      }
      if(it.desc)info.appendChild(node('p','rdesc',it.desc));
      info.appendChild(node('span','story-open review-open',url?'阅读原文 ↗':'原文链接未提供'));
      card.appendChild(media);card.appendChild(info);fragment.appendChild(card);
    });
    el.replaceChildren(fragment);
    var parent=el.closest('.card'),heading=parent&&parent.querySelector('.card-top .t');
    window.DNSPager.mount(el,{kind:'review',label:heading?heading.textContent:'图文资讯'});
  });
})();
