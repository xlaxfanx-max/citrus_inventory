document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('lot-search-form');
  const input = document.getElementById('lot-search');
  const target = document.getElementById('lots');
  const status = document.getElementById('search-status');
  let timer;
  let controller;
  let sequence = 0;

  const search = (delay = 200) => {
    clearTimeout(timer);
    controller?.abort();
    const current = ++sequence;
    // Previous matches must not remain actionable while a new query is pending.
    target.inert = true;
    target.setAttribute('aria-busy', 'true');
    status.textContent = 'Searching inventory…';
    timer = setTimeout(async () => {
      controller = new AbortController();
      const url = new URL(form.action);
      url.search = new URLSearchParams(new FormData(form)).toString();
      try {
        const response = await fetch(url, {
          headers: {'HX-Request': 'true'},
          credentials: 'same-origin',
          signal: controller.signal,
        });
        if (current !== sequence) return;
        if (response.redirected) {
          window.location.assign(response.url);
          return;
        }
        if (!response.ok) throw new Error('Search unavailable');
        const html = await response.text();
        if (current !== sequence) return;
        target.innerHTML = html;
        target.hidden = false;
        status.textContent = input.value.trim() ? 'Search results updated.' : 'Showing the full sample route.';
        window.history.replaceState(null, '', url);
      } catch (error) {
        if (current !== sequence || error.name === 'AbortError') return;
        target.hidden = true;
        status.textContent = 'Could not load lots. Check your connection and select Search to try again.';
      } finally {
        if (current === sequence) {
          target.inert = false;
          target.setAttribute('aria-busy', 'false');
        }
      }
    }, delay);
  };
  input.addEventListener('input', () => search());
  input.addEventListener('search', () => search());
  form.addEventListener('submit', event => {
    event.preventDefault();
    search(0);
  });
});
