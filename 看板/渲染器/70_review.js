// 70_review.js —— 图文预览：卡内阅读与原文外链分开，正文仍来自已有REVIEWS。
// 详情按钮交由80_details.js委托处理；不把按钮嵌在链接内、不生成不存在的摘要。
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
      var card=node('article','revcard'),media=node('div','rmedia'),info=node('div','rinfo');
      var name=String(it.name||'未命名图文'),src=imageURL(it.img);
      function placeholder(){media.replaceChildren(node('span','rthumb rnoimg',it.img?'图片待核对':d.noimg||'暂无配图'))}
      if(src){
        var img=node('img','rthumb');img.src=src;img.alt=name;img.loading='lazy';img.decoding='async';
        img.addEventListener('error',placeholder,{once:true});media.appendChild(img);
      }else placeholder();
      var title=node('h4','rname',name);title.title=name;
      // 完整标题保留在DOM与title中，主页最多两行，详情展示全名。
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
      var actions=node('div','review-actions'),preview=node('button','review-preview','查看图文');
      preview.type='button';preview.setAttribute('data-detail-review',pid);
      preview.setAttribute('data-detail-index',String(index));
      preview.setAttribute('aria-label','查看图文：'+name);actions.appendChild(preview);
      var url=webURL(it.url);
      if(url){
        var link=node('a','review-source','原文 ↗');link.href=url;link.target='_blank';link.rel='noopener noreferrer';
        link.setAttribute('aria-label','打开原文：'+name);actions.appendChild(link);
      }
      info.appendChild(actions);card.appendChild(media);card.appendChild(info);fragment.appendChild(card);
    });
    el.replaceChildren(fragment);
  });
})();
