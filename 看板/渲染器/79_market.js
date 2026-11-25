// 79_market.js —— 电商大盘翻页卡（market，v29）。
// 卡壳由组装器生成：.market > .market-tabs（页签，每页一个词条）+ .market-pages（.market-page[data-market-pid]）。
// 本文件只读 DDATA：每页按站点分列，填充主指标末值、环比/同比、月度走势（复用 drawChart）与结构指标；
// 站点缺数据显示待接入占位，不补造数值。分页复用 DNSPager（每页一个词条），左右箭头与页签等效。
(function () {
  function node(tag, cls, text) {
    var el = document.createElement(tag); if (cls) el.className = cls;
    if (text != null) el.textContent = String(text); return el;
  }
  function config(el) {
    try { return JSON.parse(el.getAttribute('data-market-config')) || {}; } catch (e) { return {}; }
  }
  function monthIndex(date) { var s = String(date || ''); return /^\d{4}-\d{2}/.test(s) ? Number(s.slice(0, 4)) * 12 + Number(s.slice(5, 7)) : NaN; }
  function fmt(v, metric) {
    if (typeof v !== 'number' || !isFinite(v)) return '—';
    var f = metric['格式'] || 'int';
    if (f === 'vol') return Math.round(v).toLocaleString('en-US');
    if (f === 'usd') return v >= 1e8 ? (v / 1e8).toFixed(2) + ' 亿美元' : v >= 1e4 ? (v / 1e4).toFixed(1) + ' 万美元' : '$' + v.toFixed(0);
    if (f === 'price') return '$' + v.toFixed(2);
    if (f === 'pct') return v.toFixed(1) + '%';
    if (f === 'rank') return '#' + Math.round(v);
    if (f === 'num1') return v.toFixed(1);
    return Math.round(v).toLocaleString('en-US');
  }
  // row[0]为数据日期，数值列从1起；列名 = 站点键 + "_" + 指标键
  function column(data, market, metric) {
    var i = data.cols.indexOf(market['键'] + '_' + metric['键']);
    return i < 0 ? -1 : i + 1;
  }
  function valid(rows, ci) {
    return rows.filter(function (r) { return typeof r[ci] === 'number' && isFinite(r[ci]); });
  }
  // 环比只对上一个自然月、同比只对去年同月计算；缺月不跨期比较。
  function change(points, ci) {
    if (points.length < 2) return null;
    var last = points[points.length - 1], li = monthIndex(last[0]), prev = points[points.length - 2];
    var mom = monthIndex(prev[0]) === li - 1 && prev[ci] ? (last[ci] - prev[ci]) / prev[ci] * 100 : null;
    var same = points.filter(function (r) { return monthIndex(r[0]) === li - 12; })[0];
    var yoy = same && same[ci] ? (last[ci] - same[ci]) / same[ci] * 100 : null;
    return { mom: mom, yoy: yoy, date: String(last[0]).slice(0, 7) };
  }
  function pill(label, value) {
    var wrap = node('span', 'mk-chg');
    wrap.appendChild(node('span', 'mk-cl', label));
    if (value === null || !isFinite(value)) { wrap.appendChild(node('span', 'mk-na', '—')); return wrap; }
    var dir = value > 0 ? 'up' : value < 0 ? 'down' : '';
    wrap.appendChild(node('span', 'dpill ' + dir, (value > 0 ? '▲ +' : value < 0 ? '▼ ' : '') + value.toFixed(1) + '%'));
    return wrap;
  }
  function buildColumn(page, market, metrics, data) {
    var col = node('article', 'mk-col'), head = node('div', 'mk-head');
    col.setAttribute('data-market', market['键']);
    head.appendChild(node('span', 'mk-name', market['名称']));
    head.appendChild(node('span', 'mk-site', market['站点']));
    col.appendChild(head);
    var main = metrics.filter(function (m) { return m['主']; })[0] || metrics[0];
    var ci = data ? column(data, market, main) : -1, points = ci > 0 ? valid(data.rows, ci) : [];
    if (!points.length) {
      col.classList.add('is-empty');
      col.appendChild(node('div', 'mk-empty', '待接入 · 暂无该站点数据'));
      return col;
    }
    var chg = change(points, ci), last = points[points.length - 1], value = last[ci];
    col.appendChild(node('div', 'mk-k', main['名称']));
    var val = node('div', 'mk-val');
    val.appendChild(node('span', 'vnum', fmt(value, main)));
    if (main['单位']) val.appendChild(node('span', 'unit', main['单位']));
    // 销额等缩写读数悬停给出未缩写原值
    val.title = main['名称'] + (chg ? ' · ' + chg.date : '') + '：' + ((main['格式'] || 'int') === 'usd' ? '$' + value.toFixed(2) : fmt(value, main) + (main['单位'] || ''));
    col.appendChild(val);
    var delta = node('div', 'mk-delta');
    delta.appendChild(pill('环比', chg ? chg.mom : null));
    delta.appendChild(pill('同比', chg ? chg.yoy : null));
    if (chg) delta.appendChild(node('span', 'mk-period', chg.date));
    col.appendChild(delta);
    var chart = node('div', 'chart');
    chart.setAttribute('data-chart', page.getAttribute('data-market-pid'));
    chart.setAttribute('data-col', String(ci));
    chart.setAttribute('aria-label', market['名称'] + ' · ' + main['名称'] + '月度走势');
    col.appendChild(chart);
    charts.push(chart);   // 纳入全局重绘列表：窗口变化时由 25_resize.js 统一重绘可见图
    // 结构指标与主指标取同一行（主指标最新有效期）：同一列的读数属于同一观测期，该期缺值显示—，不拿上期值顶替
    var stats = node('dl', 'mk-stats');
    metrics.forEach(function (m) {
      if (m === main) return;
      var ci2 = column(data, market, m), raw = ci2 > 0 ? last[ci2] : null;
      var row = node('div', 'mk-stat');
      row.appendChild(node('dt', '', m['名称']));
      row.appendChild(node('dd', '', typeof raw === 'number' && isFinite(raw) ? fmt(raw, m) : '—'));
      stats.appendChild(row);
    });
    col.appendChild(stats);
    return col;
  }
  // 隐藏页的图曾按兜底宽度绘制；只在尺寸不符或尚未绘制时重绘，避免每次滚动重画。
  function fitCharts(page) {
    page.querySelectorAll('.chart').forEach(function (el) {
      if (!el.clientWidth) return;
      var svg = el.querySelector('svg');
      if (!el.getAttribute('data-market-drawn') || (svg && Math.abs(Number(svg.getAttribute('width')) - el.clientWidth) > 1)) {
        drawChart(el, true); el.setAttribute('data-market-drawn', 'true');
      }
    });
  }
  function series(page) {
    var data = typeof DDATA !== 'undefined' ? DDATA[page.getAttribute('data-market-pid')] : null;
    return data && Array.isArray(data.rows) && data.rows.length && Array.isArray(data.cols) ? data : null;
  }
  root.querySelectorAll('[data-market]').forEach(function (box) {
    var conf = config(box), markets = conf['市场'] || [], metrics = conf['指标'] || [];
    var pages = box.querySelector('.market-pages'), tabs = box.querySelectorAll('.mtab'), card = box.closest('.card');
    var title = card && card.querySelector('.card-top .t'), action = card && card.querySelector('.detail-open');
    box.querySelectorAll('.market-page').forEach(function (page, i) {
      var data = series(page);
      markets.forEach(function (market) { page.appendChild(buildColumn(page, market, metrics, data)); });
      if (tabs[i] && data) tabs[i].classList.add('has-data');
    });
    var api = window.DNSPager.mount(pages, { kind: 'market', label: title ? title.textContent : '电商大盘', pageSize: 1,
      emptyText: '暂无数据', pageName: function (index) { var page = pages.children[index]; return page ? page.getAttribute('data-market-name') || '' : ''; } });
    if (!api) return;
    // 全部页面都没有数据时，空态不按满高占位
    if (card && !box.querySelector('.market-page .chart')) card.classList.add('market-empty');
    function pageOf(pid) {
      var found = -1;
      box.querySelectorAll('.market-page').forEach(function (page, i) { if (page.getAttribute('data-market-pid') === pid) found = i; });
      return found;
    }
    function show(index) {
      var page = pages.children[index];
      if (!page) return;
      fitCharts(page);
      tabs.forEach(function (tab, i) { tab.classList.toggle('on', i === index); tab.setAttribute('aria-pressed', i === index ? 'true' : 'false'); });
      if (action) {
        action.setAttribute('data-detail-pid', page.getAttribute('data-market-pid'));
        action.textContent = '查看「' + (page.getAttribute('data-market-name') || '') + '」完整数据';
        action.appendChild(node('span', '', '↗')).setAttribute('aria-hidden', 'true');
      }
    }
    tabs.forEach(function (tab) { tab.addEventListener('click', function () { api.goTo(Number(tab.getAttribute('data-market-tab'))); }); });
    var shown = -1;
    function sync() {
      var page = Number(pages.parentNode.getAttribute('data-page-index'));
      if (page === shown) return;
      shown = page; show(page);
    }
    sync();
    new MutationObserver(sync).observe(pages.parentNode, { attributes: true, attributeFilter: ['data-page-index'] });
    // 附录词条回跳到合并卡时翻到对应页（事件由溯源脚本在定位卡片后派发）。
    root.addEventListener('dns:focus-pid', function (event) {
      var index = pageOf(event.detail && event.detail.pid);
      if (index >= 0) api.goTo(index);
    });
  });
})();
