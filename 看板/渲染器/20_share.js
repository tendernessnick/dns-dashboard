// 20_share.js —— 主页显示最新观测期的品牌份额横条；历史数据保留在DDATA供详情查看。
var shareEls=[];
function drawShare(el){
  var pid=el.getAttribute('data-share');var d=DDATA[pid];
  function node(tag,cls,text){var target=document.createElement(tag);if(cls)target.className=cls;if(text!=null)target.textContent=String(text);return target}
  if(!d||!Array.isArray(d.rows)||!d.rows.length||!Array.isArray(d.cols)||!d.cols.length){
    el.replaceChildren(node('div','nodata','暂无有效品牌份额记录'));return;
  }
  var records=d.rows.filter(function(row){return Array.isArray(row)&&row[0]});
  if(!records.length){el.replaceChildren(node('div','nodata','暂无有效品牌份额记录'));return}
  var latest=records.reduce(function(last,row){return String(row[0])>String(last[0])?row:last},records[0]);
  var COLORS=['#235BCC','#277F93','#6D8EB4','#567183','#94A8BC','#BAC6D2'];
  var entries=d.cols.map(function(label,index){
    var value=latest[index+1];
    return {label:String(label).replace(/%$/,''),index:index,
      value:typeof value==='number'&&Number.isFinite(value)&&value>=0&&value<=100?value:null};
  });
  // 按本期份额排序，不表示排名变化、销量变化或与上期比较；缺失值置后且保留零值。
  entries.sort(function(a,b){
    if(a.value==null)return b.value==null?a.index-b.index:1;
    if(b.value==null)return -1;
    return b.value-a.value||a.index-b.index;
  });
  var meta=node('div','share-current-meta');
  meta.appendChild(node('span','share-current-date','观测日期 '+String(latest[0])));
  meta.appendChild(node('span','share-current-unit','份额（%） · 本期从高到低'));
  var list=node('ol','share-ranking');list.setAttribute('aria-label','最新一期品牌份额');
  entries.forEach(function(entry){
    var row=node('li','share-rank-row'),head=node('div','share-rank-head');
    head.appendChild(node('span','share-brand',entry.label));
    head.appendChild(node('span','share-value',entry.value==null?'—':String(entry.value)+'%'));
    var track=node('div','share-track'),fill=node('span','share-fill');
    track.setAttribute('aria-hidden','true');fill.style.display='block';fill.style.height='100%';
    fill.style.width=(entry.value==null?0:entry.value)+'%';
    fill.style.backgroundColor=COLORS[entry.index%COLORS.length];
    if(entry.value==null){row.classList.add('share-missing');row.title='该系列本期缺失或不在有效百分比范围内'}
    track.appendChild(fill);row.appendChild(head);row.appendChild(track);list.appendChild(row);
  });
  var note=node('p','share-history-note','仅展示本期份额；历史各期记录见卡片详情。横条以100%为统一基准。');
  el.replaceChildren(meta,list,note);
}
root.querySelectorAll('.sharechart').forEach(function(el){drawShare(el);shareEls.push(el)});
