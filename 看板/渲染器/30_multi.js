// 30_multi.js —— 渲染器：多品类/多SKU（data-multi：ul渲染li，strip容器渲染.sc）
root.querySelectorAll('[data-multi]').forEach(function(el){
  var pid=el.getAttribute('data-multi');var d=DDATA[pid];
  if(!d||!d.rows||!d.rows.length||!d.cols)return;
  var b=BIND[pid]||[null,null];var unit=b[0]||'';var last=d.rows[d.rows.length-1];
  if(el.tagName==='UL'){
    var html='';
    for(var i=1;i<=d.cols.length&&i<last.length;i++){var v=last[i];
      if(v===null||v===undefined)continue;
      /* v14：单位启发式——列名含%显示%，含样本/数量不标单位，其余用注册表单位 */
      var cn=String(d.cols[i-1]),u=cn.indexOf('%')>=0?'%':((cn.indexOf('样本')>=0||cn.indexOf('数量')>=0||cn.indexOf('总数')>=0)?'':unit);
      html+='<li><span>'+cn+'</span><b>'+fmtN(v,b[1])+'</b>'+(u?'<span class="mu">'+u+'</span>':'')+'</li>';}
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
