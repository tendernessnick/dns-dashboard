// 72_calendar.js —— 渲染器：议息日历动态覆盖（data-cal 锚点 ← CAL，v18.6）
// P16美联储 / P20欧洲央行：collect_P16_议息日历.py 解析官网日历与决议数据 → 议息日历.json → data.js。
// CAL 有值时覆盖模块JSON静态快照（时间线 + 说明行）；无数据时保留静态兜底不动。
// 锚点约定（v18.9统一）：data-cal 与 data-cal-desc 都存完整P号（如"P16"），与 CAL 键同名——
// v18.6的两套键（锚点存数字/CAL带P前缀）曾致静默失败，现一处同名处处同名。
(function(){
  var calendars=typeof CAL==='undefined'?{}:CAL;
  function safeUrl(value){
    try{var u=new URL(value);return /^https?:$/.test(u.protocol)?u.href:''}catch(e){return ''}
  }
  var today=new Date(),cutoff=new Date();cutoff.setDate(cutoff.getDate()-30);
  function localISO(d){return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0')}
  var upper=localISO(today),lower=localISO(cutoff);
  function itemDate(it){
    var date=String(it.iso||'').slice(0,10);
    if(!date&&/^\d{2}-\d{2}$/.test(it.date||'')){
      date=(today.getFullYear()-(it.date>upper.slice(5)?1:0))+'-'+it.date;
    }
    if(!/^\d{4}-\d{2}-\d{2}$/.test(date))return '';
    var parts=date.split('-').map(Number),parsed=new Date(parts[0],parts[1]-1,parts[2]);
    return localISO(parsed)===date&&date>=lower&&date<=upper?date:'';
  }
  function fallbackNews(pid){
    var bank=pid==='P16'?/\b(?:fed|fomc|federal reserve)\b|美联储|联邦公开市场/i:/\b(?:ecb|european central bank)\b|欧洲央行/i;
    var policy=/\b(?:fomc|monetary policy|interest rates?|discount rate|rate (?:cut|hike|decision)s?)\b|货币政策|议息|利率|加息|降息|决议|纪要/i;
    var seen={},items=[];
    Object.keys(typeof NEWS==='undefined'?{}:NEWS).forEach(function(key){
      (NEWS[key]||[]).forEach(function(it){
        var title=[it.title,it.title_zh].filter(Boolean).join(' '),url=safeUrl(it.url),date=itemDate(it);
        if(!bank.test(title)||!policy.test(title)||/non-monetary|in addition to decisions setting interest rates|非货币政策/i.test(title)||!url||seen[url]||!date)return;
        var path=new URL(url).pathname;if(!path.replace(/\//g,'')||/\/$/.test(path)||/\/(?:index|home)(?:\.[^/]+)?$/i.test(path))return;
        seen[url]=true;items.push(Object.assign({},it,{iso:date,url:url,source:it.source||new URL(url).hostname}));
      });
    });
    return items.sort(function(a,b){return b.iso.localeCompare(a.iso)});
  }
  root.querySelectorAll('[data-cal]').forEach(function(el){
    var pid=el.getAttribute('data-cal');     // 完整P号，即CAL键
    var d=calendars[pid]||{};
    if(d.时间线&&d.时间线.length){
      el.innerHTML=d.时间线.map(function(it){
        var cls=it.下一个?' class="next"':'';
        return '<li'+cls+'><b>'+escH(it.日期)+'</b>'+escH(it.文本||'')+'</li>';
      }).join('');
    }
    var card=el.closest('.card');   // desc在所在卡内找（多面板同号不漏刷）
    var desc=card&&card.querySelector('[data-cal-desc="'+pid+'"]');
    if(desc&&d.说明)desc.textContent=d.说明;
    if(!card)return;
    card.classList.add('calendar-card');
    var saved=(d.相关新闻||[]).filter(function(it){return it.title&&safeUrl(it.url)&&itemDate(it)});
    var items=saved.length?saved:fallbackNews(pid),info=d.资讯采集||{};
    var section=card.querySelector('[data-calendar-news="'+pid+'"]');
    if(!section){
      section=document.createElement('section');section.className='calendar-news';section.setAttribute('data-calendar-news',pid);
      var foot=card.querySelector('.foot');if(foot)card.insertBefore(section,foot);else card.appendChild(section);
    }
    section.innerHTML='<h4 class="calendar-news-title">相关新闻 · 近30天</h4><ul class="feed calendar-news-feed"></ul>';
    var ul=section.querySelector('ul.feed');
    if(items.length){
      ul.innerHTML=items.map(function(it){
        var zh=it.title_zh&&it.title_zh!==it.title;
        return '<li><a class="fi story-link" href="'+escH(safeUrl(it.url))+'" target="_blank" rel="noopener noreferrer">'
          +'<i class="dchip">'+escH(it.date||(it.iso||'').slice(5))+'</i><span class="story-body">'
          +'<span class="story-title"'+(zh?' title="'+escH(it.title)+'"':'')+'>'+escH(zh?it.title_zh:it.title)+'</span>'
          +'<small class="story-source">'+escH(it.source||'已有资讯')+' · 阅读原文 ↗</small></span></a></li>';
      }).join('');
      if(window.DNSPager)window.DNSPager.mount(ul,{label:(pid==='P16'?'美联储':'欧洲央行')+'相关新闻',kind:'news'});
    }else{
      ul.innerHTML='<li class="feed-empty"><span class="fi"><span>近30天暂无可展示的相关资讯</span></span></li>';
    }
    if(info.状态==='失败'){
      var notice=document.createElement('p');notice.className='calendar-news-status';
      notice.textContent=items.length?'官方资讯暂未更新，当前显示已保存条目。':'官方资讯暂未更新；会议日程与决议说明仍保留。';section.appendChild(notice);
    }
  });
})();
