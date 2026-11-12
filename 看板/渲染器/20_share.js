// 20_share.js —— 渲染器：多季度品牌份额分组柱状图（.sharechart[data-share]）
var shareEls=[];
function drawShare(el){
  var pid=el.getAttribute('data-share');var d=DDATA[pid];
  if(!d||!d.rows||!d.rows.length||!d.cols||!d.cols.length)return;
  var W=el.clientWidth||380,H=el.clientHeight||170;
  var pl=38,pr=10,pb=24;
  var rows=d.rows,n=rows.length,nb=Math.min(d.cols.length,6);
  function seriesLabel(index){return String(d.cols[index]).replace(/%$/,'')}
  // 分类色使用蓝灰谱，红绿留给其他图表的涨跌语义。
  var COLORS=['#235BCC','#557FAF','#7C9EBF','#52667F','#9BAABD','#C0CBD7'];
  var mx=0;rows.forEach(function(r){for(var i=1;i<=nb;i++)if(r[i]!=null&&r[i]>mx)mx=r[i]});
  if(!mx)mx=100;var hi=Math.ceil(mx/10)*10;
  /* v15移动端：图例按可用宽自动换行（窄容器不再画出右边界），行数决定顶部留白pt；
     桌面容器宽时仍为单行，pt=22 与 v14 一致 */
  var leg=[],lx=pl,ly=5,lrows=1;
  for(var li=0;li<nb;li++){
    var wi=11+seriesLabel(li).length*11.5+10;
    if(lx+wi>W-pr&&lx>pl){lrows++;lx=pl;ly+=17;}
    leg.push([lx,ly,li]);lx+=wi;}
  var pt=27+(lrows-1)*17;
  function Y(v){return pt+(1-v/hi)*(H-pt-pb)}
  var svg='<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" style="width:100%;height:100%;touch-action:pan-y" role="img" aria-label="按季度分组的品牌份额，单位为百分比">';
  for(var g=0;g<=4;g++){var tv=hi*g/4,yy=Y(tv);
    svg+='<line x1="'+pl+'" y1="'+yy+'" x2="'+(W-pr)+'" y2="'+yy+'" stroke="#E7EDF5" stroke-width="1"/>';
    svg+='<text class="yt" x="'+(pl-6)+'" y="'+(yy+3)+'" text-anchor="end">'+(tv%1?tv.toFixed(1):tv)+'%</text>';}
  var slot=(W-pl-pr)/n,bw=Math.max(4,Math.min(12,(slot-6)/nb));
  function qlabel(s){var m=String(s).split('-');
    if(m.length>=2){var q=Math.ceil(parseInt(m[1],10)/3);return m[0].slice(2)+'Q'+q;}
    return String(s).slice(2);}
  rows.forEach(function(r,gi){
    var gx=pl+gi*slot+(slot-nb*bw)/2;
    for(var i=0;i<nb;i++){var v=r[i+1];if(v==null)continue;
      svg+='<rect class="share-bar" data-row="'+gi+'" data-series="'+i+'" x="'+(gx+i*bw).toFixed(1)+'" y="'+Y(v).toFixed(1)+'" width="'+(bw-1.5).toFixed(1)+'" height="'+(Y(0)-Y(v)).toFixed(1)+'" rx="1" fill="'+COLORS[i]+'"><title>'+escH(r[0])+' · '+escH(seriesLabel(i))+'：'+v+'%</title></rect>';}
    svg+='<text class="xt" x="'+(pl+gi*slot+slot/2).toFixed(1)+'" y="'+(H-4)+'" text-anchor="middle">'+qlabel(r[0])+'</text>';});
  for(var i2=0;i2<leg.length;i2++){
    svg+='<rect x="'+leg[i2][0]+'" y="'+leg[i2][1]+'" width="8" height="8" rx="1.5" fill="'+COLORS[leg[i2][2]]+'"/>';
    svg+='<text class="leg" x="'+(leg[i2][0]+11)+'" y="'+(leg[i2][1]+8)+'">'+escH(seriesLabel(leg[i2][2]))+'</text>';}
  svg+='</svg>';el.innerHTML=svg;
  var tip=document.createElement('div');tip.className='ctool';el.appendChild(tip);
  function hide(){tip.style.display='none'}
  el.querySelectorAll('.share-bar').forEach(function(bar){
    function show(e){
      var row=rows[Number(bar.getAttribute('data-row'))],series=Number(bar.getAttribute('data-series'));
      var rect=el.getBoundingClientRect();if(!rect.width)return;
      tip.innerHTML='<span class="ct-date" style="display:block">'+escH(row[0])+' · '+escH(seriesLabel(series))+'</span>'
        +'<span class="ct-value"><b>'+row[series+1]+'</b> <span class="ct-unit">%</span></span>';
      tip.style.maxWidth=Math.max(1,rect.width-8)+'px';tip.style.whiteSpace='normal';tip.style.display='block';
      var x=e.clientX-rect.left+10,y=e.clientY-rect.top-tip.offsetHeight-10;
      if(x+tip.offsetWidth>rect.width-2)x=e.clientX-rect.left-tip.offsetWidth-10;
      tip.style.left=Math.max(2,Math.min(x,rect.width-tip.offsetWidth-2))+'px';
      tip.style.top=Math.max(2,Math.min(y,H-tip.offsetHeight-2))+'px';
    }
    bar.addEventListener('pointermove',show);bar.addEventListener('pointerdown',show);
    bar.addEventListener('pointerleave',hide);bar.addEventListener('pointercancel',hide);
    bar.addEventListener('pointerup',function(e){if(e.pointerType!=='mouse')hide()});
  });
}
root.querySelectorAll('.sharechart').forEach(function(el){drawShare(el);shareEls.push(el)});
