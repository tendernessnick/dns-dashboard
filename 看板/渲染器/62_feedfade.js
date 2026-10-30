// 62_feedfade.js —— 渲染器：滚动feed底部渐隐（内容溢出时提示可下滚，滚到底自动消失）
root.querySelectorAll('ul.feed').forEach(function(ul){
  function chk(){ul.classList.toggle('faded',ul.scrollTop+ul.clientHeight<ul.scrollHeight-4)}
  chk();
  ul.addEventListener('scroll',chk,{passive:true});
});
