// 20_share.js —— 渲染器：多季度品牌份额分组柱状图（.sharechart[data-share]）
var shareEls=[];
function drawShare(el){
  var pid=el.getAttribute('data-share');var d=DDATA[pid];
  if(!d||!d.rows||!d.rows.length||!d.cols||!d.cols.length)return;
  var W=el.clientWidth||380,H=el.clientHeight||170;
  var pl=30,pr=8,pb=18;
  var rows=d.rows,n=rows.length,nb=Math.min(d.cols.length,6);
  var COLORS=['#0065B0','#B45309','#0F766E','#6D28D9','#BE123C','#8A94A0'];
  var mx=0;rows.forEach(function(r){for(var i=1;i<=nb;i++)if(r[i]!=null&&r[i]>mx)mx=r[i]});
  if(!mx)mx=100;var hi=Math.ceil(mx/10)*10;
  /* v15移动端：图例按可用宽自动换行（窄容器不再画出右边界），行数决定顶部留白pt；
     桌面容器宽时仍为单行，pt=22 与 v14 一致 */
  var leg=[],lx=pl,ly=4,lrows=1;
  for(var li=0;li<nb;li++){
    var wi=11+String(d.cols[li]).length*11.5+10;
    if(lx+wi>W-pr&&lx>pl){lrows++;lx=pl;ly+=14;}
    leg.push([lx,ly,li]);lx+=wi;}
  var pt=22+(lrows-1)*14;
  function Y(v){return pt+(1-v/hi)*(H-pt-pb)}
  var svg='<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" style="width:100%;height:100%">';
  for(var g=0;g<=2;g++){var tv=hi*g/2,yy=Y(tv);
    svg+='<line x1="'+pl+'" y1="'+yy+'" x2="'+(W-pr)+'" y2="'+yy+'" stroke="#E6EBEF" stroke-width="1"/>';
    svg+='<text class="yt" x="'+(pl-4)+'" y="'+(yy+3)+'" text-anchor="end">'+Math.round(tv)+'</text>';}
  var slot=(W-pl-pr)/n,bw=Math.max(4,Math.min(12,(slot-6)/nb));
  function qlabel(s){var m=String(s).split('-');
    if(m.length>=2){var q=Math.ceil(parseInt(m[1],10)/3);return m[0].slice(2)+'Q'+q;}
    return String(s).slice(2);}
  rows.forEach(function(r,gi){
    var gx=pl+gi*slot+(slot-nb*bw)/2;
    for(var i=0;i<nb;i++){var v=r[i+1];if(v==null)continue;
      svg+='<rect x="'+(gx+i*bw).toFixed(1)+'" y="'+Y(v).toFixed(1)+'" width="'+(bw-1.5).toFixed(1)+'" height="'+(Y(0)-Y(v)).toFixed(1)+'" fill="'+COLORS[i]+'"><title>'+r[0]+' · '+d.cols[i]+'：'+v+'%</title></rect>';}
    svg+='<text class="xt" x="'+(pl+gi*slot+slot/2).toFixed(1)+'" y="'+(H-4)+'" text-anchor="middle">'+qlabel(r[0])+'</text>';});
  for(var i2=0;i2<leg.length;i2++){
    svg+='<rect x="'+leg[i2][0]+'" y="'+leg[i2][1]+'" width="8" height="8" fill="'+COLORS[leg[i2][2]]+'"/>';
    svg+='<text class="leg" x="'+(leg[i2][0]+11)+'" y="'+(leg[i2][1]+8)+'">'+d.cols[leg[i2][2]]+'</text>';}
  svg+='</svg>';el.innerHTML=svg;
}
root.querySelectorAll('.sharechart').forEach(function(el){drawShare(el);shareEls.push(el)});
