// 手动分页用于所有资讯、榜单和图文；不监听滚轮或触摸，不截留页面纵向滚动。
(function () {
  var instances = new WeakMap(), sequence = 0;
  function node(tag, cls, text) {
    var el = document.createElement(tag); if (cls) el.className = cls;
    if (text != null) el.textContent = String(text); return el;
  }
  function mount(container, options) {
    if (!container || !container.parentNode) return null;
    var existing = instances.get(container);
    if (existing) { existing.configure(options || {}); return existing; }
    var settings = Object.assign({ kind: 'news', label: '资讯', emptyText: '暂无新消息' }, options || {});
    var shell = node('div', 'content-pager'), previous = node('button', 'pager-arrow pager-previous');
    var next = node('button', 'pager-arrow pager-next'), status = node('div', 'pager-status');
    var page = 0, size = 1, lastWidth = -1, items = [], emptyState = null, pending = false;
    shell.setAttribute('role', 'region');
    if (!container.id) container.id = 'paged-content-' + (++sequence);
    container.classList.add('pager-items');
    container.setAttribute('data-pager-ready', 'true');
    previous.type = next.type = 'button';
    previous.setAttribute('aria-controls', container.id); next.setAttribute('aria-controls', container.id);
    previous.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m14 6-6 6 6 6"/></svg>';
    next.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m10 6 6 6-6 6"/></svg>';
    status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite'); status.setAttribute('aria-atomic', 'true');
    container.parentNode.insertBefore(shell, container);
    shell.appendChild(previous); shell.appendChild(container); shell.appendChild(next); shell.appendChild(status);
    function countPages() { return Math.max(1, Math.ceil(items.length / size)); }
    function safeFocus(el) { if (el && typeof el.focus === 'function') el.focus({ preventScroll: true }); }
    function focusVisibleItem() {
      var item = items.find(function (entry) { return !entry.hidden; });
      if (!item) { if (emptyState) { emptyState.setAttribute('tabindex', '-1'); safeFocus(emptyState); } return; }
      var link = item.matches('a[href],button,[tabindex]') ? item : item.querySelector('a[href],button,[tabindex]');
      if (link) safeFocus(link);
      else { item.setAttribute('tabindex', '-1'); safeFocus(item); }
    }
    function paint() {
      var total = countPages(), active = document.activeElement;
      page = Math.max(0, Math.min(page, total - 1));
      items.forEach(function (item, index) {
        item.classList.add('pager-item'); item.hidden = index < page * size || index >= (page + 1) * size;
      });
      previous.disabled = page === 0; next.disabled = page >= total - 1;
      previous.setAttribute('aria-label', settings.label + '：上一页'); next.setAttribute('aria-label', settings.label + '：下一页');
      previous.title = '上一页'; next.title = '下一页';
      shell.setAttribute('aria-label', settings.label + '分页浏览'); shell.setAttribute('data-pager-kind', settings.kind);
      shell.setAttribute('data-pager-variant', settings.variant || 'default');
      shell.setAttribute('data-page-index', String(page)); shell.setAttribute('data-page-count', String(total));
      shell.setAttribute('data-item-count', String(items.length));
      shell.classList.toggle('pager-single', total === 1);
      shell.classList.toggle('pager-empty', items.length === 0);
      shell.style.setProperty('--pager-columns', String(settings.kind === 'review' ? size : 1));
      shell.style.setProperty('--pager-page-size', String(size));
      status.textContent = !items.length ? '0 条' : total > 1 ? '第 ' + (page + 1) + ' / ' + total + ' 页 · 共 ' + items.length + ' 条' : '共 ' + items.length + ' 条';
      // 显示/收起、换页或窗口改变时，不把键盘焦点留在隐藏条目或刚禁用的按钮上。
      if (active && container.contains(active) && items.some(function (item) { return item.hidden && item.contains(active); })) focusVisibleItem();
      else if ((active === next || active === previous) && previous.disabled && next.disabled) focusVisibleItem();
      else if (active === next && next.disabled && !previous.disabled) safeFocus(previous);
      else if (active === previous && previous.disabled && !next.disabled) safeFocus(next);
    }
    function pageSize(width) {
      var requested = typeof settings.pageSize === 'function' ? settings.pageSize(width) : settings.pageSize;
      if (Number.isFinite(requested) && requested > 0) return Math.max(1, Math.floor(requested));
      if (settings.kind === 'review') return width >= 760 ? 2 : 1;
      return width < 420 ? 2 : 3;
    }
    function refresh() {
      var before = page * size, active = document.activeElement;
      var children = Array.from(container.children);
      var emptyNodes = children.filter(function (item) { return item.matches('.feed-empty,.top-empty,.rev-empty,[data-pager-empty]'); });
      items = children.filter(function (item) { return emptyNodes.indexOf(item) < 0; });
      emptyState = null;
      if (!items.length) {
        emptyState = emptyNodes.shift() || node(container.tagName === 'UL' || container.tagName === 'OL' ? 'li' : 'div');
        emptyState.className = 'pager-empty-state'; emptyState.setAttribute('data-pager-empty', 'true');
        emptyState.textContent = settings.emptyText; emptyState.hidden = false;
        if (emptyState.parentNode !== container) container.appendChild(emptyState);
      }
      emptyNodes.forEach(function (item) { item.remove(); });
      // 固定阅读槽位会截行；保留完整文本供悬停和辅助技术读取，原文链接不变。
      container.querySelectorAll('.story-title,.rname,.top-product-title,.story-summary,.rdesc,.rchips,.story-source').forEach(function (text) {
        var full = text.textContent.trim(), original = text.getAttribute('title') || '';
        if (!full || text.getAttribute('data-pager-tooltip') === full) return;
        text.title = original && original !== full && original.indexOf(full + '\n') !== 0 ? full + '\n' + original : full;
        text.setAttribute('data-pager-tooltip', full);
      });
      var focused = items.findIndex(function (item) { return item === active || item.contains(active); });
      var width = shell.getBoundingClientRect().width;
      if (width > 0) {
        var updated = pageSize(width);
        if (updated !== size) { size = updated; page = Math.floor((focused >= 0 ? focused : before) / size); }
        shell.classList.toggle('pager-compact', width < 440);
        shell.classList.toggle('pager-wide', width >= 760);
        lastWidth = width;
      }
      container.classList.remove('faded'); paint();
    }
    function schedule() {
      if (pending) return; pending = true;
      requestAnimationFrame(function () { pending = false; if (container.isConnected) refresh(); });
    }
    previous.addEventListener('click', function () { if (!previous.disabled) { page--; paint(); } });
    next.addEventListener('click', function () { if (!next.disabled) { page++; paint(); } });
    var api = {
      refresh: refresh,
      goTo: function (index) { if (Number.isFinite(index)) { page = Math.floor(index); paint(); } },
      configure: function (value) { Object.assign(settings, value); refresh(); }
    };
    instances.set(container, api); refresh();
    if (typeof ResizeObserver !== 'undefined') {
      new ResizeObserver(function (entries) {
        if (entries.some(function (entry) { return entry.contentRect.width > 0 && Math.abs(entry.contentRect.width - lastWidth) > .5; })) schedule();
      }).observe(shell);
    } else window.addEventListener('resize', schedule, { passive: true });
    // 字号偏好或字体迟到只能按阅读档位重排，不按当前页或图片固有高度量取槽位。
    if (typeof MutationObserver !== 'undefined') {
      new MutationObserver(schedule).observe(container.closest('#dns-dash') || document.documentElement, { attributes: true, attributeFilter: ['class'] });
    }
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(schedule);
    // 公司切换会先显示面板，再由下一帧重新计算页数；不修改公司选择本身。
    var panel = container.closest('[data-copanel]');
    if (panel && typeof MutationObserver !== 'undefined') new MutationObserver(schedule).observe(panel, { attributes: true, attributeFilter: ['hidden'] });
    return api;
  }
  window.DNSPager = { mount: mount };
})();
