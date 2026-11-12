// 80_details.js —— 只读模块详情：原生dialog、既有数据与明确来源，不复制业务锚点。
(function () {
  function initDetails() {
    var host = document.getElementById('dns-dash');
    if (!host || document.getElementById('moduleDetail') || !window.HTMLDialogElement) return;
    function node(tag, cls, text) {
      var el = document.createElement(tag);
      if (cls) el.className = cls;
      if (text !== undefined) el.textContent = String(text == null ? '' : text);
      return el;
    }
    var dialog = node('dialog', 'detail-dialog'); dialog.id = 'moduleDetail';
    dialog.setAttribute('aria-labelledby', 'detailTitle');
    var header = node('header', 'detail-header'), title = node('h2', 'detail-heading'); title.id = 'detailTitle';
    var close = node('button', 'detail-close', '关闭'); close.type = 'button'; close.setAttribute('aria-label', '关闭详情');
    var body = node('div', 'detail-body'), footer = node('footer', 'detail-footer');
    var bottomClose = node('button', 'detail-close-bottom', '关闭详情'); bottomClose.type = 'button';
    header.append(title, close); footer.append(node('p', 'detail-note', '数据日期与口径见各项说明。'), bottomClose);
    dialog.append(header, body, footer); host.appendChild(dialog);
    var opener = null, activeCard = null, drawJobs = [], generation = 0;

    function pid(value) {
      var m = /^P?(\d+)([a-z]?)$/i.exec(String(value || '').trim());
      return m ? 'P' + Number(m[1]) + m[2].toLowerCase() : '';
    }
    function cardPids(card) {
      var list = [];
      if (card) [card.getAttribute('data-source-pids'), card.getAttribute('data-k')].forEach(function (value) {
        String(value || '').split(/\s+/).forEach(function (part) { var p = pid(part); if (p && list.indexOf(p) < 0) list.push(p); });
      });
      return list;
    }
    function cards() { return Array.from(host.querySelectorAll('.card[data-mid],.cco[data-mid]')); }
    function visible(el) { return !!(el && el.isConnected && !el.closest('[hidden]') && el.getClientRects().length); }
    function byPid(p) {
      var found = cards().filter(function (card) { return cardPids(card).indexOf(p) >= 0; });
      return found.find(visible) || found[0] || null;
    }
    function safeLink(value) {
      try { var text = String(value || '').trim(); return /^https?:\/\//i.test(text) && /^https?:$/.test(new URL(text).protocol) ? text : ''; }
      catch (e) { return ''; }
    }
    function safeImage(value) {
      var text = String(value || '').trim();
      if (typeof MEDIA_OMISSIONS !== 'undefined' && MEDIA_OMISSIONS.indexOf(text) >= 0) return '';
      if (safeLink(text) || /^data:image\/(?:png|jpe?g|gif|webp|avif|bmp);base64,[a-z0-9+/=\s]+$/i.test(text)) return text;
      try {
        var decoded = decodeURIComponent(text).replace(/\\/g, '/');
        return /^(?:\.\/)?媒体\//.test(decoded) && !decoded.split('/').some(function (part) { return part === '..'; }) && !/[\x00-\x1f]/.test(decoded) ? text : '';
      } catch (e) { return ''; }
    }
    function link(parent, label, url) {
      var href = safeLink(url); if (!href) return;
      var a = node('a', 'detail-source-link', label); a.href = href; a.target = '_blank'; a.rel = 'noopener noreferrer'; parent.appendChild(a);
    }
    function image(parent, value, alt) {
      var src = safeImage(value); if (!src) { if (value) parent.appendChild(node('p', 'detail-note', '图片待核对，请以原文为准。')); return; }
      var img = node('img', 'detail-image'); img.src = src; img.alt = alt || ''; img.loading = 'lazy'; parent.appendChild(img);
    }
    // 仅TOPS字段在生成端已转义；一次还原后仍经textContent/URL白名单输出，不解析HTML。
    function topText(value) {
      var entities = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#x27;': "'", '&#39;': "'" };
      return String(value || '').replace(/&(?:amp|lt|gt|quot);|&#(?:x27|39);/g, function (part) { return entities[part]; });
    }
    function section(label, cls) {
      var el = node('section', 'detail-section' + (cls ? ' ' + cls : ''));
      if (label) el.appendChild(node('h3', 'detail-section-title', label)); body.appendChild(el); return el;
    }
    function textFrom(card, selector) {
      var el = card && card.querySelector(selector); return el ? el.textContent.trim() : '';
    }
    function caption(card) { return textFrom(card, '.card-top .t,.cn') || (card && card.getAttribute('data-mid')) || '资料详情'; }
    function paragraph(parent, value, cls) { if (value) parent.appendChild(node('p', cls || 'detail-note', value)); }
    function stores() {
      return { data: typeof DDATA === 'undefined' ? {} : DDATA, bind: typeof BIND === 'undefined' ? {} : BIND,
        meta: typeof META === 'undefined' ? {} : META, reviews: typeof REVIEWS === 'undefined' ? {} : REVIEWS,
        tops: typeof TOPS === 'undefined' ? {} : TOPS, news: typeof NEWS === 'undefined' ? {} : NEWS,
        prov: typeof PROV === 'undefined' ? [] : PROV };
    }
    function renderPlan(card) {
      var plan = section('功能规划', 'detail-planned'); plan.appendChild(node('span', 'chip c-planned', '规划中'));
      paragraph(plan, card.getAttribute('data-planned-id'), 'detail-meta');
      ['.plan-purpose', '.plan-content'].forEach(function (selector) { paragraph(plan, textFrom(card, selector)); });
      var fields = card.querySelectorAll('.plan-fields>span');
      if (fields.length) { var list = node('ul', 'detail-facts'); fields.forEach(function (field) { list.appendChild(node('li', '', field.textContent)); }); plan.appendChild(list); }
      card.querySelectorAll('.plan-details p').forEach(function (item) { paragraph(plan, item.textContent); });
      paragraph(plan, '尚未接入数据 · 当前仅为功能预留。');
    }
    function renderTable(parent, p, data) {
      var rows = data.rows, table = node('table', 'detail-table'); table.setAttribute('data-detail-table', p);
      var columns = data.cols || [], full = columns.length === rows[0].length;
      var names = full ? columns.slice() : ['数据日期'].concat(columns);
      while (names.length < Math.max.apply(null, rows.map(function (row) { return row.length; }))) names.push('列' + (names.length + 1));
      var cap = node('caption'), head = node('thead'), tr = node('tr'), tbody = node('tbody');
      names.forEach(function (name) { var th = node('th', '', name); th.scope = 'col'; tr.appendChild(th); }); head.appendChild(tr);
      table.append(cap, head, tbody); var wrap = node('div', 'detail-table-wrap'); wrap.tabIndex = 0;
      wrap.setAttribute('role', 'region'); wrap.setAttribute('aria-label', p + '完整历史数据表'); wrap.appendChild(table); parent.appendChild(wrap);
      var more = node('button', 'detail-load-more'); more.type = 'button'; var shown = 0, newest = rows.slice().reverse();
      function appendRows() {
        var focusMore = document.activeElement === more, stop = Math.min(shown + 50, newest.length);
        for (; shown < stop; shown++) { var row = node('tr'); names.forEach(function (_, i) {
          var value = newest[shown][i]; row.appendChild(node('td', '', value === null || value === undefined || value === '' ? '—' : String(value)));
        }); tbody.appendChild(row); }
        cap.textContent = p + ' · 已保存完整历史共 ' + rows.length + ' 行，当前显示 ' + shown + ' 行（由新到旧）';
        more.hidden = shown === rows.length; more.textContent = '加载更多（剩余 ' + (rows.length - shown) + ' 行）';
        if (focusMore && more.hidden) wrap.focus({ preventScroll: true });
      }
      more.addEventListener('click', appendRows); parent.appendChild(more); appendRows();
    }
    function renderSeries(card, p, data, state) {
      if (!data || !Array.isArray(data.rows) || !data.rows.length) return;
      var group = section(p + ' · 趋势与数据'), dates = data.rows.map(function (row) { return String(row[0] || ''); }).filter(Boolean).sort();
      var meta = state.meta[p] || {}, unit = (state.bind[p] || [])[0];
      paragraph(group, '已保存 ' + data.rows.length + ' 行 · ' + (dates[0] || '—') + ' 至 ' + (dates[dates.length - 1] || '—'), 'detail-meta');
      paragraph(group, [meta.k, unit ? '主指标单位：' + unit + '；各列以列名标注为准' : '单位以各列名称和已有口径说明为准'].filter(Boolean).join(' · '));
      var snapshot = state.tops[p], noTrend = card && card.getAttribute('data-trend') === 'none';
      var forecast = /预测|forecast/i.test((meta.k || '') + caption(card));
      if (!snapshot && !noTrend && !forecast && typeof drawChart === 'function') {
        var cols = data.cols || [], offset = cols.length === data.rows[0].length ? 0 : 1;
        var numeric = cols.map(function (name, i) { return { name: name, index: i + offset }; }).filter(function (col) {
          return col.index > 0 && !/序号|排名|名次|编号|^id$|索引/i.test(String(col.name)) &&
            data.rows.filter(function (row) { return typeof row[col.index] === 'number' && Number.isFinite(row[col.index]); }).length > 1;
        });
        if (numeric.length) {
          var chart = node('div', 'chart detail-chart'); chart.setAttribute('data-chart', p); chart.style.height = '260px';
          if (card && card.closest('[data-change="none"]')) chart.setAttribute('data-change', 'none');
          var select = node('select', 'detail-chart-select'); select.setAttribute('aria-label', p + '图表序列');
          numeric.forEach(function (col) { var option = node('option', '', col.name); option.value = String(col.index); select.appendChild(option); });
          chart.setAttribute('data-col', select.value);
          paragraph(group, '图表展示已保存完整历史；缺失数值不补点。', 'detail-meta'); group.append(select, chart);
          function draw() {
            if (!dialog.open || !chart.isConnected || chart.clientWidth <= 0) return;
            var column = Number(select.value);
            var fullRows = data.rows.filter(function (row) { return typeof row[column] === 'number' && Number.isFinite(row[column]); });
            drawChart(chart, true, { rows: fullRows, col: column, src: data.src });
            var field = numeric.find(function (col) { return String(col.index) === select.value; });
            var unitLabel = chart.querySelector('.plot-unit'); if (unitLabel) unitLabel.textContent = '字段：' + field.name;
            var hit = chart.querySelector('.hit');
            if (hit) hit.addEventListener('pointermove', function () { var shown = chart.querySelector('.ct-unit'); if (shown) shown.textContent = '字段：' + field.name; });
          }
          select.addEventListener('change', function () { chart.setAttribute('data-col', select.value); draw(); }); drawJobs.push(draw);
        }
      }
      renderTable(group, p, data);
    }
    function renderTop(p, data) {
      if (!data || !Array.isArray(data.items) || !data.items.length) return;
      var group = section(p + ' · 已保存榜单样本');
      paragraph(group, '快照 ' + (data.date || '—') + ' · 当前载荷可查看 ' + data.items.length + ' 个商品；该次样本总数 ' + (data.total == null ? '未记录' : data.total), 'detail-meta');
      paragraph(group, '商品排名与样本数量不代表实际销量、GMV或市场份额；仅展示已有快照，不补造历史商品记录。');
      data.items.forEach(function (item) {
        var article = node('article', 'detail-top-item');
        article.appendChild(node('h4', '', '第' + item.rank + '名 · ' + (topText(item.title) || '未记录标题')));
        image(article, topText(item.img), topText(item.title)); paragraph(article, '价格：' + (item.price == null ? '未记录' : '$' + item.price), 'detail-meta');
        if (/^[A-Z0-9]{10}$/i.test(item.asin || '')) link(article, '打开商品页 ↗', 'https://www.amazon.com/dp/' + item.asin);
        group.appendChild(article);
      });
    }
    function renderReviews(p, data, selected) {
      if (!data || !Array.isArray(data.items) || !data.items.length) return;
      var items = selected === null ? data.items : (data.items[selected] ? [data.items[selected]] : []);
      if (!items.length) { paragraph(section('图文资料'), '当前条目已不在已保存载荷中，请关闭后重新选择。'); return; }
      var group = section(p + ' · 图文资料');
      items.forEach(function (item) {
        var article = node('article', 'detail-review-item'); article.appendChild(node('h4', '', item.name || '未记录标题'));
        paragraph(article, [item.date, item.tag].filter(Boolean).join(' · '), 'detail-meta'); image(article, item.img, item.name);
        if (item.chips && item.chips.length) { var chips = node('div', 'detail-chips'); item.chips.forEach(function (text) { chips.appendChild(node('span', 'detail-chip', text)); }); article.appendChild(chips); }
        paragraph(article, item.desc || '当前未保存摘要，请通过原文核对。'); link(article, '打开原文 ↗', item.url); group.appendChild(article);
      });
    }
    function renderNews(card, state) {
      var keys = [];
      if (card) [card].concat(Array.from(card.querySelectorAll('[data-news]'))).forEach(function (el) {
        var key = el.getAttribute('data-news'); if (key && keys.indexOf(key) < 0) keys.push(key);
      });
      keys.forEach(function (key) {
        var items = state.news[key]; if (!Array.isArray(items) || !items.length) return;
        var group = section('已保存资讯 · ' + key);
        items.forEach(function (item) { var article = node('article', 'detail-news-item');
          article.appendChild(node('h4', '', item.title_zh || item.title || '未记录标题'));
          if (item.title_zh && item.title && item.title_zh !== item.title) paragraph(article, item.title);
          paragraph(article, item.iso || item.date, 'detail-meta'); if (item.desc || item.summary) paragraph(article, item.desc || item.summary);
          link(article, '打开原文 ↗', item.url); group.appendChild(article);
        });
      });
    }
    function renderSources(pids, state) {
      if (!pids.length) return;
      var group = section('口径与来源');
      pids.forEach(function (p) {
        var meta = state.meta[p] || {}, verify = (state.data._verify || {})[p];
        var source = state.prov.find(function (item) { return pid(item.id) === p; });
        var item = node('article', 'detail-source-item'); item.appendChild(node('h4', '', p + (source ? ' · ' + source.title : '')));
        paragraph(item, [meta.k, meta.f ? '更新频率：' + meta.f : '', meta.r ? '来源分级：' + meta.r : ''].filter(Boolean).join(' · '));
        if (verify) paragraph(item, [verify.t || (verify.s === 'sus' ? '存疑' : '核验记录'), verify.d, verify.x].filter(Boolean).join(' · '));
        if (source) {
          paragraph(item, [source.source, source.desc, source.status ? '登记状态：' + source.status : ''].filter(Boolean).join(' · '));
          link(item, '查看来源 ↗', source.url);
          if (source.method || source.note) {
            var technical = node('details', 'detail-technical'); technical.appendChild(node('summary', '', '采集与核验说明'));
            paragraph(technical, source.method ? '采集方式记录：' + source.method : '');
            paragraph(technical, source.note ? '来源备注记录：' + source.note : ''); item.appendChild(technical);
          }
        }
        else paragraph(item, (state.data[p] && state.data[p].src) || '当前载荷未登记可展示的来源详情。');
        group.appendChild(item);
      });
    }
    function renderDescription(card) {
      if (!card) return;
      var texts = ['.sub', '.desc', '.cd', '.research-note', '.usage-note', '.usage-hint', '.data-note'].map(function (selector) { return textFrom(card, selector); }).filter(Boolean);
      var links = Array.from(card.querySelectorAll('a[href]')).filter(function (a) { return safeLink(a.getAttribute('href')); });
      if (!texts.length && !links.length) return;
      var group = section('已有说明与查询入口'); [...new Set(texts)].forEach(function (text) { paragraph(group, text); });
      links.forEach(function (a) { link(group, a.textContent.trim() || '打开原始来源 ↗', a.getAttribute('href')); });
    }
    function openDetails(trigger) {
      var state = stores(), wanted = trigger.getAttribute('data-detail-module'), review = pid(trigger.getAttribute('data-detail-review'));
      var top = pid(trigger.getAttribute('data-detail-top')), requested = pid(trigger.getAttribute('data-detail-pid'));
      var card = wanted ? cards().find(function (item) { return item.getAttribute('data-mid') === wanted; }) : byPid(review || top || requested);
      if (!card) return; // P号入口必须命中本页真实依赖，不从模块数字或任意字符串捏造详情。
      opener = trigger; activeCard = card; generation++; drawJobs = []; body.replaceChildren(); title.textContent = caption(card);
      if (card && card.getAttribute('data-module-status') === 'planned') renderPlan(card);
      else {
        var pids = cardPids(card);
        if ([review, top, requested].some(function (p) { return p && pids.indexOf(p) < 0; })) return;
        if (requested) {
          pids = [requested];
          var source = state.prov.find(function (item) { return pid(item.id) === requested; });
          if (source && source.title) title.textContent = source.title;
        }
        var indexText = trigger.getAttribute('data-detail-index'), index = /^\d+$/.test(indexText || '') ? Number(indexText) : null;
        if (review) renderReviews(review, state.reviews[review], index);
        else {
          var mediaCard = card.querySelector('[data-review],[data-toplist]');
          if (!requested) {
            if (mediaCard || top) paragraph(body, textFrom(card, '.research-note')); else renderDescription(card);
          }
          pids.forEach(function (p) { renderTop(p, state.tops[p]); renderReviews(p, state.reviews[p], null); renderSeries(card, p, state.data[p], state); });
          if (!requested) renderNews(card, state);
        }
        renderSources(pids, state);
        if (!body.childElementCount) paragraph(section('资料状态'), '当前未保存可展开的内容，请结合原卡说明与来源入口核对。');
      }
      if (!dialog.open) dialog.showModal(); body.scrollTop = 0; close.focus();
      var token = generation; requestAnimationFrame(function () { if (token === generation) drawJobs.forEach(function (draw) { draw(); }); });
    }
    function shut() { if (dialog.open) dialog.close(); }
    close.addEventListener('click', shut); bottomClose.addEventListener('click', shut);
    dialog.addEventListener('keydown', function (event) {
      if (event.key === '/' || event.key === 'Escape') event.stopPropagation();
      if (event.key !== 'Tab' || event.isComposing) return;
      // 原生modal保留inert/Esc；显式首尾循环避免Chrome将Tab焦点交给浏览器外壳。
      var focusable = Array.from(dialog.querySelectorAll('button,a[href],input,select,textarea,summary,[tabindex]')).filter(function (el) {
        return el.tabIndex >= 0 && !el.matches(':disabled') && !el.closest('[hidden],[inert]') && el.getClientRects().length &&
          getComputedStyle(el).visibility !== 'hidden';
      });
      if (!focusable.length) { event.preventDefault(); close.focus(); return; }
      var index = focusable.indexOf(document.activeElement), next = null;
      if (index < 0) next = focusable[0];
      else if (event.shiftKey && index === 0) next = focusable[focusable.length - 1];
      else if (!event.shiftKey && index === focusable.length - 1) next = focusable[0];
      if (next) { event.preventDefault(); next.focus(); }
    });
    dialog.addEventListener('close', function () {
      generation++; drawJobs = []; body.replaceChildren();
      var fallback = document.getElementById('moduleSearch') || host.querySelector('a[data-dashboard-page][aria-current="page"]');
      var target = visible(opener) && (!activeCard || visible(activeCard)) ? opener : fallback;
      opener = null; activeCard = null; if (visible(target)) target.focus({ preventScroll: true });
    });
    host.addEventListener('click', function (event) {
      var trigger = event.target.closest && event.target.closest('button[data-detail-module],button[data-detail-pid],button[data-detail-review],button[data-detail-top]');
      if (trigger && !dialog.contains(trigger)) openDetails(trigger);
    });
    window.addEventListener('resize', function () { if (dialog.open) requestAnimationFrame(function () { drawJobs.forEach(function (draw) { draw(); }); }); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initDetails, { once: true }); else initDetails();
})();
