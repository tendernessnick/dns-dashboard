// 30_multi.js —— 渲染器：多品类/多SKU（data-multi：ul渲染li，strip容器渲染.sc）
root.querySelectorAll('[data-multi]').forEach(function(el){
  var pid=el.getAttribute('data-multi');var d=DDATA[pid];
  if(!d||!d.rows||!d.rows.length||!d.cols)return;
  var b=BIND[pid]||[null,null];var unit=b[0]||'';var last=d.rows[d.rows.length-1];
  if(el.tagName==='UL'){
    var html='';
    for(var i=1;i<=d.cols.length&&i<last.length;i++){var v=last[i];
      if(v===null||v===undefined)continue;
      html+='<li><span>'+d.cols[i-1]+'</span><b>'+fmtN(v,b[1])+'</b>'+(unit?'<span class="mu">'+unit+'</span>':'')+'</li>';}
    if(html)el.innerHTML=html;
  }else{
    var note=el.querySelector('[data-multi-note]');
    for(var j=1;j<=d.cols.length&&j<last.length;j++){var v2=last[j];
      if(v2===null||v2===undefined)continue;
      var sc=document.createElement('div');sc.className='sc';
      sc.innerHTML='<span class="k">'+d.cols[j-1]+'</span><span class="v"><span class="vnum">'+fmtN(v2,b[1])+'</span>'+(unit?'<small>'+unit+'</small>':'')+'</span><span class="s">'+last[0]+'</span>';
      el.insertBefore(sc,note||null);}
  }
});
