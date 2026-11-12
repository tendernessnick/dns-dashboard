// 75_workspace.js —— 本页模块检索与定位；不筛掉卡片，不改数据、布局或溯源。
(function () {
  function initWorkspaceSearch() {
    var workspaceRoot = document.getElementById('dns-dash');
    var input = document.getElementById('moduleSearch');
    var results = document.getElementById('moduleSearchResults');
    var clearButton = document.getElementById('clearModuleSearch');
    var overview = document.getElementById('workspaceOverview');
    if (!workspaceRoot || !input || !results || !clearButton || !overview) return;
    if (input.getAttribute('data-workspace-search-ready') === 'true') return;

    var maxResults = 8;
    var composing = false;
    var selectedCard = null;
    var addedTabindex = false;

    function normalized(value) {
      return String(value || '').replace(/\s+/g, ' ').trim().toLowerCase();
    }

    function normalizedPid(value) {
      var match = /^P?(\d+)([a-z]?)$/i.exec(String(value || '').trim());
      return match ? 'p' + Number(match[1]) + match[2].toLowerCase() : '';
    }

    // 只索引标题和身份信息。图文正文、新闻标题和数据说明均不进入检索语料。
    var entries = Array.prototype.map.call(workspaceRoot.querySelectorAll('.card[data-mid],.cco[data-mid]'), function (card) {
      var moduleId = card.getAttribute('data-mid') || '';
      var titleNode = card.querySelector('.card-top .t,.cn');
      var title = (titleNode ? titleNode.textContent : moduleId).trim();
      var section = card.closest('.mod');
      var sectionTitle = section && section.querySelector('.sec-head h2');
      var sectionName = sectionTitle ? sectionTitle.textContent.trim() : '本页模块';
      var panel = card.closest('[data-copanel]');
      var company = panel ? panel.getAttribute('data-copanel') : '';
      var moduleNumber = /^(\d+)(?:_|$)/.exec(moduleId);
      var plannedPid = card.getAttribute('data-planned-id') || '';
      var pids = [];
      [plannedPid, card.getAttribute('data-k'), card.getAttribute('data-source-pids')].forEach(function (value) {
        String(value || '').split(/\s+/).forEach(function (part) {
          var pid = normalizedPid(part);
          if (pid && pids.indexOf(pid) < 0) pids.push(pid);
        });
      });
      var sourceLabel = pids.map(function (pid) { return pid.replace(/^p/, 'P'); }).join(' / ');
      var numberLabel = '模块 ' + (moduleNumber ? moduleNumber[1] : moduleId);
      var detail = [sectionName, company, plannedPid ? '规划预留 ' + plannedPid : (sourceLabel || numberLabel)].filter(Boolean).join(' · ');
      return { card: card, id: card.id, moduleId: moduleId, title: title, detail: detail,
        pids: pids, text: normalized([title, moduleId, sectionName, company].join(' ')) };
    }).filter(function (entry) { return entry.id && entry.moduleId; });

    function clearSelection() {
      if (selectedCard) {
        selectedCard.classList.remove('workspace-highlight');
        if (addedTabindex && selectedCard.getAttribute('tabindex') === '-1') selectedCard.removeAttribute('tabindex');
      }
      selectedCard = null;
      addedTabindex = false;
    }

    function collapseResults() {
      results.hidden = true;
      input.setAttribute('aria-expanded', 'false');
      overview.setAttribute('data-search-active', 'false');
    }

    function jumpTo(entry) {
      var card = entry.card;
      if (!card.isConnected) return;
      var panel = card.closest('[data-copanel]');
      if (panel && panel.hidden) {
        var scope = panel.closest('.mod') || workspaceRoot;
        var company = panel.getAttribute('data-copanel');
        var buttons = scope.querySelectorAll('[data-cotab]');
        for (var i = 0; i < buttons.length; i++) {
          if (buttons[i].getAttribute('data-cotab') === company) {
            buttons[i].click();
            break;
          }
        }
        if (panel.hidden) return; // 缺失切换控件时不手改面板状态，也不聚焦隐藏内容。
      }
      // 先收起工具栏下拉再定位，保留关键词供再次聚焦或继续输入时检索。
      collapseResults();
      clearSelection();
      selectedCard = card;
      addedTabindex = !card.hasAttribute('tabindex');
      if (addedTabindex) card.setAttribute('tabindex', '-1');
      card.classList.add('workspace-highlight');
      window.requestAnimationFrame(function () {
        if (selectedCard !== card || !card.isConnected) return;
        var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        card.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'center', inline: 'nearest' });
        card.focus({ preventScroll: true });
      });
    }

    function renderResults() {
      var query = normalized(input.value);
      results.replaceChildren();
      clearButton.hidden = !input.value;
      results.hidden = !query;
      input.setAttribute('aria-expanded', query ? 'true' : 'false');
      overview.setAttribute('data-search-active', query ? 'true' : 'false');
      if (!query) {
        results.setAttribute('data-match-count', '0');
        return;
      }

      var terms = query.split(' ');
      var matches = entries.filter(function (entry) {
        return terms.every(function (term) {
          // 完整P号作精确匹配，避免P2同时命中P20/P201；普通文字仍支持片段检索。
          return /^p\d+[a-z]?$/i.test(term)
            ? entry.pids.indexOf(normalizedPid(term)) >= 0 : entry.text.indexOf(term) >= 0;
        });
      });
      results.setAttribute('data-match-count', String(matches.length));
      var summary = document.createElement('p');
      summary.className = matches.length ? 'workspace-search-summary' : 'workspace-search-empty';
      summary.textContent = matches.length
        ? '找到 ' + matches.length + ' 个模块' + (matches.length > maxResults ? '，显示前 ' + maxResults + ' 项；继续输入可缩小范围。' : '。')
        : '未找到匹配模块，请尝试卡名、编号或板块名称。';
      results.appendChild(summary);
      if (!matches.length) return;

      var list = document.createElement('ul');
      list.className = 'workspace-search-list';
      matches.slice(0, maxResults).forEach(function (entry) {
        var item = document.createElement('li');
        item.className = 'workspace-search-item';
        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'workspace-search-result';
        button.setAttribute('data-workspace-target', entry.id);
        button.setAttribute('data-module-id', entry.moduleId);
        button.setAttribute('aria-controls', entry.id);
        var title = document.createElement('span');
        title.className = 'workspace-result-title';
        title.textContent = entry.title;
        var detail = document.createElement('span');
        detail.className = 'workspace-result-meta';
        detail.textContent = entry.detail;
        button.appendChild(title);
        button.appendChild(detail);
        button.addEventListener('click', function () { jumpTo(entry); });
        item.appendChild(button);
        list.appendChild(item);
      });
      results.appendChild(list);
    }

    function clearSearch(restoreFocus) {
      input.value = '';
      clearSelection();
      renderResults();
      if (restoreFocus) input.focus();
    }

    function isEditing(target) {
      if (!target || target.nodeType !== 1) return false;
      return /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName) || target.isContentEditable ||
        !!target.closest('[role="textbox"]');
    }

    input.setAttribute('aria-controls', results.id);
    results.setAttribute('aria-live', 'polite');
    results.setAttribute('aria-atomic', 'true');
    input.addEventListener('focus', function () { if (!composing) renderResults(); });
    input.addEventListener('compositionstart', function () { composing = true; });
    input.addEventListener('compositionend', function () { composing = false; renderResults(); });
    input.addEventListener('input', function (event) {
      if (!composing && !event.isComposing) renderResults();
    });
    clearButton.addEventListener('click', function () { clearSearch(true); });
    document.addEventListener('keydown', function (event) {
      if (event.defaultPrevented || event.isComposing || composing || event.keyCode === 229 ||
          event.ctrlKey || event.metaKey || event.altKey) return;
      if (event.key === '/' && !isEditing(event.target)) {
        event.preventDefault();
        input.focus();
        return;
      }
      if (event.key === 'Escape' && input.value) {
        if (isEditing(event.target) && event.target !== input) return;
        var fromResults = results.contains(event.target);
        clearSearch(fromResults || event.target === input);
        if (fromResults || event.target === input) event.preventDefault();
      }
    });
    renderResults();
    input.setAttribute('data-workspace-search-ready', 'true');
  }

  // 旧骨架在ENGINE之后补卡片DOM id；等页面初始化完毕再建索引，缺失新控件则安全退出。
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initWorkspaceSearch, { once: true });
  else initWorkspaceSearch();
})();
