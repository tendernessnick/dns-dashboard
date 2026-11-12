// 15_chart.js —— 分析终端折线图：轻网格、实际日期、静态末值与分层查值。
// 取数/窗口/纵轴范围与原版一致；红绿只表达可比较序列的区间涨跌。
// 累计/预测等data-change=none序列使用品牌蓝，不显示前值差。
var charts=[],v8seq=0;
function v8cols(){var cs=getComputedStyle(root);
  return{up:(cs.getPropertyValue('--up')||'#B42318').trim()||'#B42318',
         down:(cs.getPropertyValue('--down')||'#0E7A54').trim()||'#0E7A54',
         base:(cs.getPropertyValue('--brand')||'#235BCC').trim()||'#235BCC',
         grid:(cs.getPropertyValue('--n100')||'#E6ECF4').trim()||'#E6ECF4',
         muted:(cs.getPropertyValue('--n500')||'#65758B').trim()||'#65758B'}}
function drawChart(el,redraw,seriesOverride){
  var key=el.getAttribute('data-chart');
  var ci=parseInt(el.getAttribute('data-col')||'1',10)||1;
  var s=seriesOverride||getSeries(key,ci);
  if(!s||s.rows.length<2){el.innerHTML='<div class="nodata">有效数据点不足 · 累积后展示趋势</div>';return;}
  var b=BIND[key]||[null,null];
  var W=el.clientWidth||300,H=el.clientHeight||118;
  var mini=H<150;
  var pl=mini?44:52,pr=mini?58:66,pt=22,pb=mini?24:28,n=s.rows.length;
  var vals=s.rows.map(function(r){return r[ci]});
  var mn=Math.min.apply(null,vals),mx=Math.max.apply(null,vals);
  var rg=(mx-mn)||Math.abs(mx)*0.02||1,lo=mn-rg*0.15,hi=mx+rg*0.15;
  function X(i){return pl+i*(W-pl-pr)/(n-1)}
  function Y(v){return pt+(1-(v-lo)/(hi-lo))*(H-pt-pb)}
  // 仅缩短实际日期的显示宽度，不推断日频/月频或填造观测期。
  function XL(t){t=String(t);return /^\d{4}-\d{2}-\d{2}$/.test(t)&&W<500?t.slice(2):t}
  function dec(){return (b[1]==null)?2:b[1]}
  var CC=v8cols(),isUp=vals[n-1]>=vals[0],comparable=canCompare(el);
  var c=comparable&&vals[n-1]!==vals[0]?(isUp?CC.up:CC.down):CC.base;
  pl=Math.max(pl,Math.max(fmtT(lo).length,fmtT(hi).length)*5.6+10);
  var chipT=fmtN(vals[n-1],dec()),cw=chipT.length*(mini?7.2:7.8)+14,chh=20;
  pr=Math.max(pr,cw+10);
  var gid='v8g'+(++v8seq);
  var svg='<svg class="redraw terminal-plot" width="'+W+'" height="'+H+'" viewBox="0 0 '+W+' '+H+'" role="img" aria-label="时间序列，悬停或左右滑动查看实际日期与数值">';
  svg+='<text class="plot-unit" x="'+pl+'" y="11" style="font-size:12px;fill:'+CC.muted+'">'+escH(b[0]?('单位：'+b[0]):'')+'</text>';
  svg+='<text class="plot-meta" x="'+(W-pr)+'" y="11" text-anchor="end" style="font-size:12px;fill:'+CC.muted+'">'+n+' 个数据点</text>';
  var span=hi-lo,rawStep=span/(mini?3:3.5),mag=Math.pow(10,Math.floor(Math.log(rawStep)/Math.LN10));
  var nm=rawStep/mag,step=(nm>=5?10:nm>=2?5:nm>=1?2:1)*mag;
  for(var tv=Math.ceil(lo/step)*step,i2=0;tv<=hi+1e-9;tv=(Math.ceil(lo/step)*step+(++i2)*step)){
    var yy=Y(tv);
    svg+='<line class="grid" x1="'+pl+'" y1="'+yy+'" x2="'+(W-pr)+'" y2="'+yy+'" style="stroke:'+CC.grid+';stroke-width:1"/>';
    svg+='<text x="'+(pl-6)+'" y="'+(yy+3.5)+'" text-anchor="end">'+fmtT(tv)+'</text>';
  }
  /* 期初基准虚线（窗口首值，类昨收线） */
  var y0=Y(vals[0]);
  svg+='<line class="baseline" x1="'+pl+'" y1="'+y0.toFixed(1)+'" x2="'+(W-pr)+'" y2="'+y0.toFixed(1)+'"/>';
  if(!mini)svg+='<text class="baselabel" x="'+(pl+4)+'" y="'+(y0-4).toFixed(1)+'">期初 '+fmtT(vals[0])+'</text>';
  /* 轻面积 + 实线，无描画和呼吸动画。 */
  var pts=s.rows.map(function(r,i){return [X(i),Y(r[ci])]});
  var line=pts.map(function(p){return p[0].toFixed(1)+','+p[1].toFixed(1)}).join(' ');
  svg+='<defs><linearGradient id="'+gid+'" x1="0" y1="0" x2="0" y2="1">'
    +'<stop offset="0" stop-color="'+c+'" stop-opacity=".07"/>'
    +'<stop offset="1" stop-color="'+c+'" stop-opacity="0"/></linearGradient></defs>';
  svg+='<polygon class="area-a" fill="url(#'+gid+')" points="'+pl+','+(H-pb)+' '+line+' '+(W-pr)+','+(H-pb)+'"/>';
  svg+='<polyline class="line-a" fill="none" stroke="'+c+'" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round" points="'+line+'"/>';
  /* 最高/最低点标注（小图省略） */
  if(!mini&&W>=400){
    var imx=0,imn=0;vals.forEach(function(v,i){if(v>vals[imx])imx=i;if(v<vals[imn])imn=i});
    if(imx!==imn){
      [[imx,-7],[imn,15]].forEach(function(m){
        var i=m[0],dy=m[1];if(i===0||i===n-1)return;
        svg+='<circle class="minmax" cx="'+pts[i][0].toFixed(1)+'" cy="'+pts[i][1].toFixed(1)+'" r="2.6" stroke="'+c+'"/>';
        svg+='<text class="mmlabel" x="'+pts[i][0].toFixed(1)+'" y="'+(pts[i][1]+dy).toFixed(1)+'" text-anchor="middle">'+fmtT(vals[i])+'</text>';
      });
    }
  }
  /* 静态末值：描边标记保持数值清晰，颜色只反映区间涨跌。 */
  var lx=pts[n-1][0],ly=pts[n-1][1];
  svg+='<circle class="last-point" cx="'+lx.toFixed(1)+'" cy="'+ly.toFixed(1)+'" r="3" fill="#fff" stroke="'+c+'" stroke-width="1.7"/>';
  var cy=Math.max(pt+chh/2+1,Math.min(H-pb-chh/2-1,ly));
  svg+='<g class="chip-a"><rect class="chiprect" x="'+(W-cw-3).toFixed(1)+'" y="'+(cy-chh/2).toFixed(1)+'" width="'+cw.toFixed(1)+'" height="'+chh+'" rx="4" style="fill:#FFF;stroke:'+c+';stroke-opacity:.35;stroke-width:1"/>'
    +'<text class="chiptext" x="'+(W-3-cw/2).toFixed(1)+'" y="'+(cy+3.5).toFixed(1)+'" text-anchor="middle" style="fill:'+c+';font-size:12px;font-weight:600">'+escH(chipT)+'</text></g>';
  var lb=(W-pl-pr<190||n<3)?[0,n-1]:[0,Math.floor((n-1)/2),n-1];
  for(var li=0;li<lb.length;li++){var i3=lb[li];
    var a=i3===0?'start':(i3===n-1?'end':'middle');
    svg+='<text class="plot-date" x="'+X(i3).toFixed(1)+'" y="'+(H-5)+'" text-anchor="'+a+'" style="font-size:12px">'+escH(XL(s.rows[i3][0]))+'<title>'+escH(s.rows[i3][0])+'</title></text>';
  }
  svg+='<line class="guide" x1="0" y1="'+pt+'" x2="0" y2="'+(H-pb)+'" style="display:none"/>';
  svg+='<circle class="hdot" r="4.5" style="display:none"/>';
  svg+='<rect class="hit" x="0" y="0" width="'+W+'" height="'+H+'"/>';
  svg+='</svg>';
  var tip=document.createElement('div');tip.className='ctool';
  el.innerHTML=svg;el.appendChild(tip);
  var gl=el.querySelector('.guide'),hd=el.querySelector('.hdot'),hit=el.querySelector('.hit');
  function v8hideTick(){tip.style.display='none';gl.style.display='none';hd.style.display='none'}
  hit.addEventListener('pointermove',function(e){
    var r=el.getBoundingClientRect();if(!r.width)return;
    var x=(e.clientX-r.left)/r.width*W;
    var i=Math.round((x-pl)/((W-pl-pr)/(n-1)));i=Math.max(0,Math.min(n-1,i));
    var px=X(i),py=Y(s.rows[i][ci]);
    gl.setAttribute('x1',px);gl.setAttribute('x2',px);gl.style.display='block';
    hd.setAttribute('cx',px);hd.setAttribute('cy',py);hd.setAttribute('stroke',c);hd.style.display='block';
  var dtxt='';if(i>0&&comparable){var dd=Math.round((s.rows[i][ci]-s.rows[i-1][ci])*Math.pow(10,dec()))/Math.pow(10,dec());
      dtxt='<span class="d '+(dd>=0?'up':'down')+'">（较前期 '+(dd>=0?'+':'')+dd+'）</span>';}
    tip.innerHTML='<span class="ct-date" style="display:block">'+escH(s.rows[i][0])+'</span>'
      +'<span class="ct-value"><b>'+fmtN(s.rows[i][ci],dec())+'</b> <span class="ct-unit">'+escH(b[0]||'')+'</span></span>'
      +(dtxt?'<span style="display:block">'+dtxt+'</span>':'');
    tip.style.maxWidth=Math.max(1,W-8)+'px';tip.style.whiteSpace='normal';
    tip.style.display='block';
    var tx=px+10;if(tx+tip.offsetWidth>W-2)tx=px-tip.offsetWidth-10;
    tx=Math.max(2,Math.min(tx,W-tip.offsetWidth-2));
    var ty=py-tip.offsetHeight-10;if(ty<2)ty=py+10;
    tip.style.left=tx+'px';tip.style.top=Math.max(2,Math.min(ty,H-tip.offsetHeight-2))+'px';
  });
  hit.addEventListener('pointerleave',v8hideTick);
  /* v15移动端：触摸抬手/系统中断（滚页面接管）时收尾提示；.hit 的 touch-action:pan-y
     保证竖扫滚页面、横扫刷数值两种手势并存（样式见 _style.css v15段） */
  hit.addEventListener('pointercancel',v8hideTick);
  hit.addEventListener('pointerup',function(e){if(e.pointerType!=='mouse')v8hideTick()});
}
root.querySelectorAll('.chart').forEach(function(el){drawChart(el);charts.push(el)});
