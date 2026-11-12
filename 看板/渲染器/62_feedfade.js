// 兼容榜单和静态资讯列表：统一分页，不再使用滚动渐隐或内部纵向滚动。
root.querySelectorAll('ul.feed').forEach(function (ul) {
  if (ul.getAttribute('data-pager-ready') === 'true') return;
  var card = ul.closest('.card'), title = card && card.querySelector('.card-top .t');
  window.DNSPager.mount(ul, { kind: ul.hasAttribute('data-toplist') ? 'toplist' : 'news', label: title ? title.textContent : '资讯' });
});
