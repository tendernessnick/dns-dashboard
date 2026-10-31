// 65_nav.js —— 渲染器：导航高亮（IntersectionObserver）+ 回顶按钮
// v16：卡片滚动入场（一次性；REDUCE/无IO 时回退v14行为，绝不隐藏内容）
(function(){
  if(window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches)return;
  if(!('IntersectionObserver' in window))return;
  var els=[].slice.call(root.querySelectorAll('.card,.cco'));
  if(!els.length)return;
  root.classList.add('js-anim');
  var io=new IntersectionObserver(function(es){
    es.forEach(function(e){if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}});
  },{rootMargin:'0px 0px 96px 0px'});
  els.forEach(function(el){
    if(el.getBoundingClientRect().top<window.innerHeight+80){el.classList.add('in')}
    else{io.observe(el)}
  });
})();
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
