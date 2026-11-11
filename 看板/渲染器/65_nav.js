// 65_nav.js —— 渲染器：导航高亮（IntersectionObserver）+ 回顶按钮
// v21：卡片直接可见，去除滚动入场；导航保留当前位置与键盘语义。
var links=[].slice.call(root.querySelectorAll('#dnav a'));
var secs=links.map(function(a){return root.querySelector(a.getAttribute('href'))}).filter(Boolean);
function mark(id){links.forEach(function(a){var active=a.getAttribute('href')==='#'+id;
  a.classList.toggle('on',active);if(active)a.setAttribute('aria-current','location');else a.removeAttribute('aria-current');})}
var btn=root.querySelector('#toTop');
var navFrame=0;
function updateNav(){
  navFrame=0;
  if(secs.length){var current=secs[0],edge=Math.min(window.innerHeight*.35,250);
    secs.forEach(function(s){if(s.getBoundingClientRect().top<=edge)current=s});mark(current.id);}
  btn.style.display=window.scrollY>500?'block':'none';
}
function queueNav(){if(!navFrame)navFrame=requestAnimationFrame(updateNav)}
window.addEventListener('scroll',queueNav,{passive:true});
window.addEventListener('resize',queueNav,{passive:true});
updateNav();
btn.addEventListener('click',function(){window.scrollTo({top:0,behavior:'smooth'})});
// v18.7：外链卡片委托点击——组装器b_hlines不再注入内联onclick，改data-href属性统一在此打开
root.addEventListener('click',function(ev){
  var el=ev.target.closest?ev.target.closest('[data-href]'):null;
  if(el){window.open(el.getAttribute('data-href'),'_blank','noopener')}
});
