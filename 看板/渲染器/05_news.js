// 资讯/公告改为可直接打开原文的卡片，用左右按钮分页，数据保持只读。
(function () {
  function node(tag, cls, text) {
    var el = document.createElement(tag); if (cls) el.className = cls;
    if (text != null) el.textContent = String(text); return el;
  }
  function webURL(value) {
    var text = String(value || '').trim(); if (!/^https?:\/\//i.test(text)) return '';
    try { var url = new URL(text); return /^https?:$/.test(url.protocol) ? url.href : ''; } catch (_) { return ''; }
  }
  root.querySelectorAll('[data-news]').forEach(function (el) {
    var ul = el.matches('ul.feed') ? el : el.querySelector('ul.feed'); if (!ul) return;
    var items = NEWS[el.getAttribute('data-news')], fragment = document.createDocumentFragment();
    if (Array.isArray(items)) items.forEach(function (it) {
      if (!it || typeof it !== 'object') return;
      var title = String(it.title_zh || it.title || '未记录标题'), url = webURL(it.url);
      var item = node('li', 'news-item'), link = node(url ? 'a' : 'div', 'fi story-link');
      if (url) { link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer'; link.setAttribute('aria-label', '打开原文：' + title); }
      var meta = node('span', 'story-meta');
      meta.appendChild(node('i', 'dchip', it.iso || it.date || '日期未提供'));
      if (it.source) meta.appendChild(node('span', 'story-source', it.source));
      meta.appendChild(node('span', 'story-open', url ? '原文 ↗' : '原文链接未提供'));
      link.appendChild(meta);
      var heading = node('span', 'story-title', title); heading.title = it.title || title; link.appendChild(heading);
      if (it.desc || it.summary) link.appendChild(node('span', 'story-summary', it.desc || it.summary));
      item.appendChild(link); fragment.appendChild(item);
    });
    if (!fragment.childNodes.length) fragment.appendChild(node('li', 'feed-empty', '当前无可展示资讯 · 更新与异常状态见数据溯源'));
    ul.replaceChildren(fragment);
    var title = el.querySelector('.card-top .t');
    window.DNSPager.mount(ul, { kind: 'news', label: title ? title.textContent : '资讯' });
  });
})();
