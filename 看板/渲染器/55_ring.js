// 55_ring.js —— 渲染器：Qi2环形图（[data-ring]：col1=Qi2数 col2=全库总数 col3=Qi2.2(25W)数）
// 静态蓝/灰蓝双环；col3(Qi2.2)/全库仍使用原口径，颜色不表达涨跌。
(function(){
  var brand=(getComputedStyle(root).getPropertyValue('--brand')||'#235BCC').trim();
  var C=188.5;
  function labelRing(ring,label){
    ring.setAttribute('role','img');ring.setAttribute('aria-label',label);
    var svg=ring.querySelector('svg');
    if(svg){svg.setAttribute('role','img');svg.setAttribute('aria-label',label)}
  }
  function clearRing(el,reason){
    el.querySelectorAll('.rf').forEach(function(arc){
      arc.style.transition='none';arc.setAttribute('stroke-dasharray','0 '+C);
    });
    el.querySelectorAll('.rt').forEach(function(value){value.textContent='—'});
    el.querySelectorAll('.ring').forEach(function(ring,index){
      labelRing(ring,(index===0?'Qi2（MPP）':'Qi2.2（25W）')+'认证占全库比例：暂无有效数据');
    });
    var rv=el.querySelector('.rv');if(rv)rv.textContent='暂无有效认证数据';
    var rs=el.querySelector('.rs');if(rs)rs.textContent=reason;
  }
  root.querySelectorAll('[data-ring]').forEach(function(el){
    var d=DDATA[el.getAttribute('data-ring')];
    if(!d||!Array.isArray(d.rows)||!d.rows.length||!d.cols||d.cols.length<2){
      clearRing(el,'当前无可用认证记录，暂不展示占比。');return;
    }
    var last=d.rows[d.rows.length-1],qi2=last[1],tot=last[2],qi22=last[3];
    if(!Number.isFinite(qi2)||!Number.isFinite(tot)||tot<=0){
      clearRing(el,'当前记录的认证数或全库总数无效，暂不展示占比。');return;
    }
    if(!Number.isFinite(qi22))qi22=null;
    var pct=Math.round(qi2/tot*100);
    var pcts=[pct];
    if(qi22!=null&&el.querySelector('.rf.ralt'))pcts.push(Math.round(qi22/tot*100));   // v19.1：第二环=Qi2.2占全库
    var rfs=el.querySelectorAll('.rf'),rts=el.querySelectorAll('.rt');
    for(var i=0;i<rfs.length;i++){
      var percent=pcts[i];
      rfs[i].style.stroke=i===0?brand:'#829AB8';
      rfs[i].style.transition='none';
      rfs[i].setAttribute('stroke-dasharray',(percent==null?'0':(C*percent/100).toFixed(1))+' '+C);
      var ring=rfs[i].closest('.ring');
      if(ring){
        labelRing(ring,(i===0?'Qi2（MPP）':'Qi2.2（25W）')+'认证占全库比例：'+
          (percent==null?'当前观测无数据':percent+'%')+'；观测日期'+last[0]);
      }
    }
    for(var j=0;j<rts.length;j++){
      rts[j].textContent=pcts[j]==null?'—':pcts[j]+'%';
    }
    var rv=el.querySelector('.rv');if(rv)rv.textContent=fmtN(qi2,0)+' / '+fmtN(tot,0)+' 条';
    var sub='Qi2（MPP）认证累计 · 观测日期'+String(last[0]);
    if(qi22!=null)sub+=' · 其中Qi2.2(25W) '+fmtN(qi22,0)+'条';   // v19：Qi2.2认证数(25W)列
    var rs=el.querySelector('.rs');if(rs)rs.textContent=sub;
  });
})();
