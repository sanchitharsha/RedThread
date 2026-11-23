// Tabs: ARIA tablist; panels stay hidden until their tab is clicked.
document.querySelectorAll('[role=tablist]').forEach(function (list) {
  var tabs = list.querySelectorAll('[role=tab]');
  tabs.forEach(function (tab) {
    tab.addEventListener('click', function () {
      tabs.forEach(function (t) {
        var on = t === tab;
        t.setAttribute('aria-selected', on ? 'true' : 'false');
        var p = document.getElementById(t.getAttribute('aria-controls'));
        if (p) { p.hidden = !on; }
      });
      var panel = document.getElementById(tab.getAttribute('aria-controls'));
      if (panel && panel.dataset.render === 'spec' && !panel.dataset.done) {
        // Specifications are rendered by JavaScript on first open (L01).
        var rows = (window.SPEC_DATA || []).map(function (r) {
          return '<tr><th scope="row">' + r[0] + '</th><td>' + r[1] + '</td></tr>';
        }).join('');
        panel.innerHTML = '<table>' + rows + '</table>';
        panel.dataset.done = '1';
      }
    });
  });
});

// Cookie banner
(function () {
  var b = document.getElementById('cookie');
  if (!b) { return; }
  var seen = false;
  try { seen = sessionStorage.getItem('cookie-ok') === '1'; } catch (e) {}
  if (seen) { b.hidden = true; }
  b.querySelector('button').addEventListener('click', function () {
    b.hidden = true;
    try { sessionStorage.setItem('cookie-ok', '1'); } catch (e) {}
  });
})();

// Search: client-side filter by brand / model / name. Any matching word counts; best matches first.
(function () {
  var q = document.getElementById('q');
  var go = document.getElementById('go');
  var list = document.getElementById('results');
  var count = document.getElementById('result-count');
  var norm = function (s) { return (s || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim(); };
  var squash = function (s) { return (s || '').toLowerCase().replace(/[^a-z0-9]/g, ''); };
  function run() {
    if (!list) { return; }
    var words = norm(q.value).split(' ').filter(Boolean);
    var shown = 0;
    var items = Array.prototype.slice.call(list.children);
    items.forEach(function (li) {
      var hay = norm(li.dataset.search), flat = squash(li.dataset.search), score = 0;
      words.forEach(function (w) { if (hay.indexOf(w) > -1 || flat.indexOf(squash(w)) > -1) { score++; } });
      li.dataset.score = score;
      li.hidden = words.length > 0 && score === 0;
      if (!li.hidden) { shown++; }
    });
    items.sort(function (a, b) { return b.dataset.score - a.dataset.score || a.dataset.order - b.dataset.order; })
         .forEach(function (li) { list.appendChild(li); });
    if (count) { count.textContent = shown + (shown === 1 ? ' product' : ' products'); }
  }
  if (!q) { return; }
  var init = new URLSearchParams(location.search).get('q');
  if (init) { q.value = init; }
  q.addEventListener('input', run);
  q.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); run(); } });
  if (go) { go.addEventListener('click', run); }
  run();
})();
