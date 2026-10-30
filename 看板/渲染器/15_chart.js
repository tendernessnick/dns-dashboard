// 15_chart.js —— 渲染器：行情风交互折线图（.chart[data-chart]，真实日期轴+悬停）
// v14：线色随窗口区间涨红/跌绿、渐变面积、期初基准虚线、尾点呼吸圈、最新价chip、描画动画
// 小图（H<150）自动精简：省略最高/最低标注与期初文字，chip 缩小
var charts=[],v8seq=0;
var V8REDUCE=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
function v8cols(){var cs=getComputedStyle(root);
  return{up:(cs.getPropertyValue('--up')||'#B42318').trim()||'#B42318',
         down:(cs.getPropertyValue('--down')||'#0E7A54').trim()||'#0E7A54'}}
function drawChart(el,redraw){
  var key=el.getAttribute('data-chart');
  var ci=parseInt(el.getAttribute('data-col')||'1',10)||1;
  var s=getSeries(key,ci);
  if(!s||s.rows.length<2){el.innerHTML='<div class="nodata">数据积累中 · 自2026-10-23起按频率记录，正式序列生成后自动绘制</div>';return;}
  var b=BIND[key]||[null,null];
  var W=el.clientWidth||300,H=el.clientHeight||118;
  var mini=H<150;
  var pl=mini?44:52,pr=mini?58:66,pt=mini?10:16,pb=mini?18:24,n=s.rows.length;
  var vals=s.rows.map(function(r){return r[ci]});
  var mn=Math.min.apply(null,vals),mx=Math.max.apply(null,vals);
  var rg=(mx-mn)||Math.abs(mx)*0.02||1,lo=mn-rg*0.15,hi=mx+rg*0.15;
  function X(i){return pl+i*(W-pl-pr)/(n-1)}
  function Y(v){return pt+(1-(v-lo)/(hi-lo))*(H-pt-pb)}
  function XL(t){return t.length>=10?t.slice(0,7):t}
  function dec(){return (b[1]==null)?2:b[1]}
  var CC=v8cols(),isUp=vals[n-1]>=vals[0],c=isUp?CC.up:CC.down;
  var gid='v8g'+(++v8seq);
  var svg='<svg'+((redraw||V8REDUCE)?' class="redraw"':'')+' width="'+W+'" height="'+H+'" viewBox="0 0 '+W+' '+H+'" role="img" aria-label="历史趋势，悬停查看数值">';
  var span=hi-lo,rawStep=span/(mini?3:3.5),mag=Math.pow(10,Math.floor(Math.log(rawStep)/Math.LN10));
  var nm=rawStep/mag,step=(nm>=5?10:nm>=2?5:nm>=1?2:1)*mag;
  for(var tv=Math.ceil(lo/step)*step,i2=0;tv<=hi+1e-9;tv=(Math.ceil(lo/step)*step+(++i2)*step)){
    var yy=Y(tv);
    svg+='<line class="grid" x1="'+pl+'" y1="'+yy+'" x2="'+(W-pr)+'" y2="'+yy+'"/>';
    svg+='<text x="'+(pl-6)+'" y="'+(yy+3.5)+'" text-anchor="end">'+fmtT(tv)+'</text>';
  }
  /* 期初基准虚线（窗口首值，类昨收线） */
  var y0=Y(vals[0]);
  svg+='<line class="baseline" x1="'+pl+'" y1="'+y0.toFixed(1)+'" x2="'+(W-pr)+'" y2="'+y0.toFixed(1)+'"/>';
  if(!mini)svg+='<text class="baselabel" x="'+(pl+4)+'" y="'+(y0-4).toFixed(1)+'">期初 '+fmtT(vals[0])+'</text>';
  /* 渐变面积 + 主线（描画动画：pathLength=1） */
  var pts=s.rows.map(function(r,i){return [X(i),Y(r[ci])]});
  var line=pts.map(function(p){return p[0].toFixed(1)+','+p[1].toFixed(1)}).join(' ');
  svg+='<defs><linearGradient id="'+gid+'" x1="0" y1="0" x2="0" y2="1">'
    +'<stop offset="0" stop-color="'+c+'" stop-opacity=".20"/>'
    +'<stop offset="1" stop-color="'+c+'" stop-opacity="0"/></linearGradient></defs>';
  svg+='<polygon class="area-a" fill="url(#'+gid+')" points="'+pl+','+(H-pb)+' '+line+' '+(W-pr)+','+(H-pb)+'"/>';
  svg+='<polyline class="line-a" pathLength="1" fill="none" stroke="'+c+'" stroke-width="2.25" stroke-linejoin="round" stroke-linecap="round" points="'+line+'"/>';
  /* 最高/最低点标注（小图省略） */
  if(!mini){
    var imx=0,imn=0;vals.forEach(function(v,i){if(v>vals[imx])imx=i;if(v<vals[imn])imn=i});
    if(imx!==imn){
      [[imx,-7],[imn,15]].forEach(function(m){
        var i=m[0],dy=m[1];if(i===0||i===n-1)return;
        svg+='<circle class="minmax" cx="'+pts[i][0].toFixed(1)+'" cy="'+pts[i][1].toFixed(1)+'" r="2.6" stroke="'+c+'"/>';
        svg+='<text class="mmlabel" x="'+pts[i][0].toFixed(1)+'" y="'+(pts[i][1]+dy).toFixed(1)+'" text-anchor="middle">'+fmtT(vals[i])+'</text>';
      });
    }
  }
  /* 尾点：实心点 + 呼吸圈 + 最新价chip */
  var lx=pts[n-1][0],ly=pts[n-1][1];
  svg+='<circle cx="'+lx.toFixed(1)+'" cy="'+ly.toFixed(1)+'" r="3" fill="#fff" stroke="'+c+'" stroke-width="2"/>';
  svg+='<circle cx="'+lx.toFixed(1)+'" cy="'+ly.toFixed(1)+'" r="3" fill="none" stroke="'+c+'" stroke-width="1.5">'
    +'<animate attributeName="r" values="3;10" dur="1.8s" repeatCount="indefinite"/>'
    +'<animate attributeName="opacity" values=".55;0" dur="1.8s" repeatCount="indefinite"/></circle>';
  var chipT=fmtN(vals[n-1],dec()),cw=chipT.length*(mini?6.6:7.4)+(mini?10:14),chh=mini?16:20;
  var cy=Math.max(pt+chh/2+1,Math.min(H-pb-chh/2-1,ly));
  svg+='<g class="chip-a"><rect class="chiprect" x="'+(W-cw-3).toFixed(1)+'" y="'+(cy-chh/2).toFixed(1)+'" width="'+cw.toFixed(1)+'" height="'+chh+'" rx="5" fill="'+c+'"/>'
    +'<text class="chiptext" x="'+(W-3-cw/2).toFixed(1)+'" y="'+(cy+3.5).toFixed(1)+'" text-anchor="middle" font-size="'+(mini?10:11)+'">'+chipT+'</text></g>';
  var lb=[0,Math.floor((n-1)/2),n-1];
  for(var li=0;li<lb.length;li++){var i3=lb[li];
    var a=i3===0?'start':(i3===n-1?'end':'middle');
    svg+='<text x="'+X(i3).toFixed(1)+'" y="'+(H-4)+'" text-anchor="'+a+'">'+XL(s.rows[i3][0])+'</text>';
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
    var px=X(i),py=Y(s.rows[i][ci]);
    gl.setAttribute('x1',px);gl.setAttribute('x2',px);gl.style.display='block';
    hd.setAttribute('cx',px);hd.setAttribute('cy',py);hd.setAttribute('stroke',c);hd.style.display='block';
    var dtxt='';if(i>0){var dd=Math.round((s.rows[i][ci]-s.rows[i-1][ci])*Math.pow(10,dec()))/Math.pow(10,dec());
      dtxt='<span class="d '+(dd>=0?'up':'down')+'">（较前期 '+(dd>=0?'+':'')+dd+'）</span>';}
    tip.innerHTML=escH(s.rows[i][0])+' · <b>'+fmtN(s.rows[i][ci],dec())+'</b> '+escH(b[0]||'')+dtxt;
    tip.style.display='block';
    var tx=px+10;if(tx+tip.offsetWidth>W-2)tx=px-tip.offsetWidth-10;
    tip.style.left=tx+'px';tip.style.top=Math.max(2,py-tip.offsetHeight-10)+'px';
  });
  hit.addEventListener('pointerleave',function(){tip.style.display='none';
    gl.style.display='none';hd.style.display='none'});
}
root.querySelectorAll('.chart').forEach(function(el){drawChart(el);charts.push(el)});
