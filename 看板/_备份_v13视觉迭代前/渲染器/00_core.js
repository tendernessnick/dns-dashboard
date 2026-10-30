// 00_core.js —— 核心层：根节点/数据契约/格式化/取数（渲染器的公共依赖）
// 契约：ACCENT/DDATA 由 data.js 先行加载；本文件只定义变量与纯函数，无DOM副作用
var root=document.getElementById('dns-dash');
if(!root)throw new Error('root missing');
var BIND=DDATA._bind||{};delete DDATA._bind;
// 显示窗口：每词条默认截取最近N点（WIN），工具栏「周期」选择器可临时覆盖
var WIN=DDATA._win||{};delete DDATA._win;
var PSEL=null;
function wind(pid,rows){
  if(PSEL==='all')return rows;
  if(PSEL&&PSEL.months){
    var t=new Date();t.setMonth(t.getMonth()-PSEL.months);
    var cs=t.getFullYear()+'-'+('0'+(t.getMonth()+1)).slice(-2)+'-01';
    var f=rows.filter(function(r){return r[0]>=cs});
    if(f.length>=2)return f;
  }
  var n=WIN[pid];
  return (n&&rows.length>n)?rows.slice(-n):rows;
}
// 资讯/公告feed：由 DDATA._news（data.js）渲染进 data-news 锚点
var NEWS=DDATA._news||{};delete DDATA._news;
// 数据治理元数据（可靠度/口径/待补录/数据截至，来自词条注册表，保留供溯源脚本使用）
var META=DDATA._meta||{}, PEND=DDATA._pending||{}, ASOF=DDATA._asof||'';
function escH(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
  .replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
// 数值格式化
function fmtN(v,d){d=(d===undefined)?(Math.abs(v)>=1000?0:2):d;
  var s=Math.abs(v)>=1000?Math.round(v).toLocaleString('en-US'):v.toFixed(d);
  return s;}
function fmtT(v){var a=Math.abs(v);if(a>=1000)return Math.round(v).toLocaleString('en-US');
  if(a>=100)return String(Math.round(v));if(a>=10)return String(Math.round(v*10)/10);
  return String(Math.round(v*100)/100)}
function getSeries(pid,col){col=col||1;var d=DDATA[pid];if(!d||!d.rows||!d.rows.length)return null;
  var rows=d.rows.filter(function(r){return r[col]!==null&&r[col]!==undefined});
  rows=wind(pid,rows);
  return rows.length?{rows:rows,col:col,src:d.src}:null;}
