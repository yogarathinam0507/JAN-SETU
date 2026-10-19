// Runs before first paint (loaded synchronously) so there is no light/dark flash.
(function () {
  var pref = 'system';
  try { pref = localStorage.getItem('jansetu.theme') || 'system'; } catch (e) { /* storage blocked */ }
  var dark = pref === 'dark' || (pref === 'system' && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  document.documentElement.setAttribute('data-theme-pref', pref);
  try { var fs = localStorage.getItem('jansetu.font'); if (fs) document.documentElement.setAttribute('data-font', fs); } catch (e) { /* */ }
})();
