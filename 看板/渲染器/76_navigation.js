// 可收缩目录：桌面保留编号快捷入口，窄屏使用紧凑的展开菜单。
(function () {
  function initNavigation() {
    var dash = document.getElementById('dns-dash');
    var rail = document.getElementById('workspaceNavigation');
    var nav = document.getElementById('dnav');
    var toggle = document.getElementById('navigationToggle');
    var current = document.getElementById('navigationCurrent');
    if (!dash || !rail || !nav || !toggle || dash.dataset.navigationReady) return;

    var storageKey = 'dns.dashboard.navigation.v1';
    var memoryKey = '__DNS_DASHBOARD_NAVIGATION_V1__';
    var desktop = window.matchMedia('(min-width: 1280px)');
    var preference = { desktopCollapsed: false, mobileOpen: false };
    var links = Array.prototype.slice.call(nav.querySelectorAll('a[href^="#"]'));
    var label = toggle.querySelector('.rail-toggle-label');

    function readPreference(value) {
      if (!value || typeof value !== 'object') return;
      if (typeof value.desktopCollapsed === 'boolean') preference.desktopCollapsed = value.desktopCollapsed;
      if (typeof value.mobileOpen === 'boolean') preference.mobileOpen = value.mobileOpen;
    }
    // file://、受限存储和分享版srcdoc均允许安全降级为当前窗口的内存状态。
    try { readPreference(JSON.parse(window.localStorage.getItem(storageKey))); } catch (error) {}
    try { readPreference(window.parent[memoryKey]); } catch (error) {}
    try { readPreference(window[memoryKey]); } catch (error) {}

    function savePreference() {
      var saved = { desktopCollapsed: preference.desktopCollapsed, mobileOpen: preference.mobileOpen };
      try { window.localStorage.setItem(storageKey, JSON.stringify(saved)); } catch (error) {}
      try { window[memoryKey] = saved; } catch (error) {}
      // 分享版换部门时iframe会重建，父窗口中的轻量状态仍可复用。
      try { window.parent[memoryKey] = saved; } catch (error) {}
    }

    function redrawLayout() {
      // 使用现有的可见图表重绘与导航更新入口，避免生成第二套图表状态。
      window.requestAnimationFrame(function () { window.dispatchEvent(new Event('resize')); });
    }

    function applyState(redraw) {
      var isDesktop = desktop.matches;
      var expanded = isDesktop ? !preference.desktopCollapsed : preference.mobileOpen;
      var activeWasHidden = !isDesktop && !expanded && nav.contains(document.activeElement);
      dash.setAttribute('data-nav-collapsed', String(isDesktop && preference.desktopCollapsed));
      dash.setAttribute('data-mobile-nav-open', String(!isDesktop && preference.mobileOpen));
      nav.hidden = !isDesktop && !expanded;
      toggle.setAttribute('aria-expanded', String(expanded));
      toggle.setAttribute('aria-label', expanded ? '收起目录' : '展开目录');
      toggle.title = expanded ? '收起目录' : '展开目录';
      label.textContent = isDesktop ? (expanded ? '收起' : '展开') : (expanded ? '收起目录' : '展开目录');
      if (activeWasHidden) toggle.focus({ preventScroll: true });
      if (redraw) redrawLayout();
    }

    function closeMobile(restoreFocus) {
      if (desktop.matches || !preference.mobileOpen) return;
      preference.mobileOpen = false;
      applyState(false);
      savePreference();
      if (restoreFocus) toggle.focus({ preventScroll: true });
    }

    links.forEach(function (link) {
      var name = link.querySelector('.nav-label');
      var number = link.querySelector('.nav-no');
      var count = link.querySelector('.nav-count');
      var fullName = [number && number.textContent.trim(), name && name.textContent.trim()].filter(Boolean).join(' · ');
      if (count && count.textContent.trim()) fullName += '（' + count.textContent.trim() + '个模块）';
      link.setAttribute('aria-label', fullName);
      link.title = fullName;
      link.addEventListener('click', function (event) {
        if (desktop.matches || event.defaultPrevented || event.button > 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        closeMobile(false);
        // 收起后仍保留原生锚点/历史行为，将键盘焦点交给被定位板块。
        var target = document.getElementById(link.getAttribute('href').slice(1));
        if (!target) return;
        window.requestAnimationFrame(function () {
          var temporary = !target.hasAttribute('tabindex');
          if (temporary) target.setAttribute('tabindex', '-1');
          target.focus({ preventScroll: true });
          if (temporary) target.addEventListener('blur', function removeTemporaryFocus() {
            if (target.getAttribute('tabindex') === '-1') target.removeAttribute('tabindex');
          }, { once: true });
        });
      });
    });

    function updateCurrent() {
      var active = nav.querySelector('a[aria-current="location"] .nav-label');
      current.textContent = active ? active.textContent.trim() : '快速定位板块';
    }
    var observer = new MutationObserver(updateCurrent);
    observer.observe(nav, { subtree: true, attributes: true, attributeFilter: ['aria-current'] });

    toggle.addEventListener('click', function () {
      if (desktop.matches) preference.desktopCollapsed = !preference.desktopCollapsed;
      else preference.mobileOpen = !preference.mobileOpen;
      applyState(desktop.matches);
      savePreference();
    });
    document.addEventListener('pointerdown', function (event) {
      if (!rail.contains(event.target)) closeMobile(false);
    });
    document.addEventListener('keydown', function (event) {
      if (event.key !== 'Escape' || event.isComposing || event.defaultPrevented ||
          desktop.matches || !preference.mobileOpen || document.querySelector('dialog[open]')) return;
      event.preventDefault();
      event.stopPropagation();
      closeMobile(true);
    }, true);
    function changeViewport() { applyState(true); }
    if (desktop.addEventListener) desktop.addEventListener('change', changeViewport);
    else desktop.addListener(changeViewport);

    dash.setAttribute('data-navigation-ready', 'true');
    toggle.hidden = false;
    applyState(true);
    updateCurrent();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initNavigation, { once: true });
  else initNavigation();
})();
