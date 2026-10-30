// 15_chart.js —— 渲染器：交互折线图（.chart[data-chart]，真实日期轴+悬停）
var charts=[];
function drawChart(el){
  var key=el.getAttribute('data-chart');
  var ci=parseInt(el.getAttribute('data-col')||'1',10)||1;
  var s=getSeries(key,ci);
  if(!s||s.rows.length<2){el.innerHTML='<div class="nodata">数据积累中 · 自2026-10-23起按频率记录，正式序列生成后自动绘制</div>';return;}
  var b=BIND[key]||[null,null];
  var W=el.clientWidth||300,H=el.clientHeight||100;
  var pl=46,pr=14,pt=12,pb=20,n=s.rows.length;
  var vals=s.rows.map(function(r){return r[ci]});
  var mn=Math.min.apply(null,vals),mx=Math.max.apply(null,vals);
  var rg=(mx-mn)||Math.abs(mx)*0.02||1,lo=mn-rg*0.18,hi=mx+rg*0.18;
  function X(i){return pl+i*(W-pl-pr)/(n-1)}
  function Y(v){return pt+(1-(v-lo)/(hi-lo))*(H-pt-pb)}
  function XL(s){return s.length>=10?s.slice(0,7):s}
  var acc=getComputedStyle(el.closest('.mod')||el).getPropertyValue('--acc').trim()||'#0065B0';
  var svg='<svg width="'+W+'" height="'+H+'" viewBox="0 0 '+W+' '+H+'" role="img" aria-label="历史趋势，悬停查看数值">';
  var span=hi-lo,rawStep=span/3,mag=Math.pow(10,Math.floor(Math.log(rawStep)/Math.LN10));
  var nm=rawStep/mag,step=(nm>=5?10:nm>=2?5:nm>=1?2:1)*mag;
  for(var tv=Math.ceil(lo/step)*step,i2=0;tv<=hi+1e-9;tv=(Math.ceil(lo/step)*step+(++i2)*step)){
    var yy=Y(tv);
    svg+='<line class="grid" x1="'+pl+'" y1="'+yy+'" x2="'+(W-pr)+'" y2="'+yy+'"/>';
    svg+='<text x="'+(pl-6)+'" y="'+(yy+3.5)+'" text-anchor="end">'+fmtT(tv)+'</text>';
  }
  var pts=s.rows.map(function(r,i){return [X(i),Y(r[ci])]});
  var line=pts.map(function(p){return p[0].toFixed(1)+','+p[1].toFixed(1)}).join(' ');
  svg+='<polygon class="area" points="'+pl+','+(H-pb)+' '+line+' '+(W-pr)+','+(H-pb)+'"/>';
  svg+='<polyline class="line" style="stroke:'+acc+'" points="'+line+'"/>';
  svg+='<circle class="lastdot" style="stroke:'+acc+'" cx="'+pts[n-1][0]+'" cy="'+pts[n-1][1]+'" r="3.2"/>';
  svg+='<text class="lastv" style="fill:'+acc+'" x="'+Math.min(pts[n-1][0]-4,W-4)+'" y="'+(pts[n-1][1]-7)+'" text-anchor="end">'+fmtN(vals[n-1],b[1])+'</text>';
  var lb=[0,Math.floor((n-1)/2),n-1];
  for(var li=0;li<lb.length;li++){var i3=lb[li];
    var a=i3===0?'start':(i3===n-1?'end':'middle');
    svg+='<text x="'+X(i3)+'" y="'+(H-4)+'" text-anchor="'+a+'">'+XL(s.rows[i3][0])+'</text>';
  }
  svg+='<line class="guide" x1="0" y1="'+pt+'" x2="0" y2="'+(H-pb)+'" style="display:none"/>';
  svg+='<circle class="hdot" r="4" style="display:none"/>';
  svg+='<rect class="hit" x="0" y="0" width="'+W+'" height="'+H+'"/>';
  svg+='</svg>';
  var tip=document.createElement('div');tip.className='ctool';
  el.innerHTML=svg;el.appendChild(tip);
  var gl=el.querySelector('.guide'),hd=el.querySelector('.hdot'),hit=el.querySelector('.hit');
  hit.addEventListener('pointermove',function(e){
    var r=el.getBoundingClientRect();var x=e.clientX-r.left;
    var i=Math.round((x-pl)/((W-pl-pr)/(n-1)));i=Math.max(0,Math.min(n-1,i));
    var px=X(i),py=Y(s.rows[i][1]);
    gl.setAttribute('x1',px);gl.setAttribute('x2',px);gl.style.display='block';
    hd.setAttribute('cx',px);hd.setAttribute('cy',py);hd.style.display='block';
    var dtxt='';if(i>0){var dd=Math.round((s.rows[i][ci]-s.rows[i-1][ci])*100)/100;
      dtxt='（较前期 '+(dd>=0?'+':'')+dd+'）'}
    tip.innerHTML=s.rows[i][0]+' · <b>'+fmtN(s.rows[i][ci],b[1])+'</b> '+b[0]+dtxt;
    tip.style.display='block';
    var tx=px+10;if(tx+tip.offsetWidth>W-2)tx=px-tip.offsetWidth-10;
    tip.style.left=tx+'px';tip.style.top=Math.max(2,py-tip.offsetHeight-10)+'px';
  });
  hit.addEventListener('pointerleave',function(){tip.style.display='none';
    gl.style.display='none';hd.style.display='none'});
}
root.querySelectorAll('.chart').forEach(function(el){drawChart(el);charts.push(el)});
