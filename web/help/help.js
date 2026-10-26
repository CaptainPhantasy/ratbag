(() => {
  'use strict';
  const theme = document.querySelector('#help-theme');
  const search = document.querySelector('#help-search');
  const clear = document.querySelector('#clear-search');
  const result = document.querySelector('#search-result');
  const noResults = document.querySelector('#no-results');
  const sections = [...document.querySelectorAll('[data-help-section]')];
  const links = [...document.querySelectorAll('[data-section-link]')];
  const knownThemes = new Set(['system', 'dark', 'light', 'contrast']);
  const matching = sections.map(section => ({ section, text: section.textContent.toLocaleLowerCase() }));
  let selectedTheme = 'system';

  function readTheme() {
    try {
      const saved = localStorage.getItem('swarm.theme');
      if (knownThemes.has(saved)) return saved;
    } catch (_) { /* Help remains usable when browser storage is unavailable. */ }
    return 'system';
  }

  function applyTheme(value) {
    selectedTheme = knownThemes.has(value) ? value : 'system';
    if (selectedTheme === 'system') delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = selectedTheme;
    if (theme) theme.value = selectedTheme;
  }

  applyTheme(readTheme());
  theme?.addEventListener('change', () => {
    applyTheme(theme.value);
    try { localStorage.setItem('swarm.theme', selectedTheme); } catch (_) { /* Session choice still applies. */ }
  });
  window.addEventListener('storage', event => {
    if (event.key === 'swarm.theme' || event.key === null) applyTheme(readTheme());
  });

  function filterSections() {
    const query = search.value.trim().toLocaleLowerCase();
    const terms = query.split(/\s+/).filter(Boolean);
    const visible = new Set();
    for (const item of matching) {
      const keep = terms.every(term => item.text.includes(term));
      item.section.hidden = !keep;
      if (keep) visible.add(item.section.id);
    }
    for (const link of links) link.hidden = !visible.has(link.dataset.sectionLink);
    clear.hidden = !query;
    noResults.hidden = visible.size > 0;
    result.textContent = query ? `${visible.size} of ${sections.length} sections match.` : `${sections.length} sections. Search this guide or choose a heading.`;
  }

  search?.addEventListener('input', filterSections);
  clear?.addEventListener('click', () => { search.value = ''; filterSections(); search.focus(); });
  document.querySelector('#search-controls').hidden = false;
  filterSections();

  function highlightSection() {
    let identifier = '';
    try { identifier = decodeURIComponent(location.hash.slice(1)); } catch (_) { identifier = ''; }
    for (const link of links) {
      if (link.dataset.sectionLink === identifier) link.setAttribute('aria-current', 'true');
      else link.removeAttribute('aria-current');
    }
    const target = sections.find(section => section.id === identifier);
    if (target?.hidden) {
      search.value = '';
      filterSections();
      target.scrollIntoView();
    }
  }
  window.addEventListener('hashchange', highlightSection);
  highlightSection();
  const print = document.querySelector('#print-guide');
  print.hidden = false;
  print.addEventListener('click', () => window.print());
})();
