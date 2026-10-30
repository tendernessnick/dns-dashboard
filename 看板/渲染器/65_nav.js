// 65_nav.js —— 渲染器：导航高亮（IntersectionObserver）+ 回顶按钮
var links=[].slice.call(root.querySelectorAll('#dnav a'));
var secs=links.map(function(a){return root.querySelector(a.getAttribute('href'))}).filter(Boolean);
function mark(id){links.forEach(function(a){a.classList.toggle('on',a.getAttribute('href')==='#'+id)})}
if('IntersectionObserver' in window && secs.length){
  var io=new IntersectionObserver(function(es){
    es.forEach(function(e){if(e.isIntersecting)mark(e.target.id)});
  },{rootMargin:'-40% 0px -55% 0px'});
  secs.forEach(function(s){io.observe(s)});
}
var btn=root.querySelector('#toTop');
window.addEventListener('scroll',function(){btn.style.display=window.scrollY>500?'block':'none'},{passive:true});
btn.addEventListener('click',function(){window.scrollTo({top:0,behavior:'smooth'})});
