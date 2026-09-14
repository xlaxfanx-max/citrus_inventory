// Save plan decisions in place. Every form marked data-decision posts with
// fetch and swaps the returned decision box into both the table row and the
// phone card for that recommendation. Without scripts the forms still submit
// normally and the page reloads.
document.addEventListener('submit', async event => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement) || !form.hasAttribute('data-decision')) return;
  if (!window.fetch || !window.FormData) return;
  event.preventDefault();
  const box = form.closest('[data-decision-for]');
  const recId = box && box.getAttribute('data-decision-for');
  const buttons = form.querySelectorAll('button');
  buttons.forEach(b => { b.disabled = true; });
  try {
    const response = await fetch(form.action, {
      method: 'POST',
      body: new FormData(form),
      headers: {'HX-Request': 'true'},
      credentials: 'same-origin',
    });
    if (response.redirected) { window.location.assign(response.url); return; }
    if (response.status !== 200 && response.status !== 400) throw new Error('Save failed');
    const html = await response.text();
    const template = document.createElement('template');
    template.innerHTML = html.trim();
    const fresh = template.content.firstElementChild;
    document.querySelectorAll(`[data-decision-for="${recId}"]`).forEach(node => {
      node.replaceWith(fresh.cloneNode(true));
    });
    const coverage = response.headers.get('X-Plan-Coverage');
    if (coverage) {
      const counts = JSON.parse(coverage);
      Object.entries(counts).forEach(([key, value]) => {
        document.querySelectorAll(`[data-coverage="${key}"]`).forEach(el => { el.textContent = value; });
      });
      const undecidedTile = document.querySelector('[data-coverage="undecided"]')?.closest('.tile');
      if (undecidedTile) undecidedTile.classList.toggle('amber', counts.undecided > 0);
      const reasonsTile = document.querySelector('[data-coverage-reasons]');
      if (reasonsTile) {
        reasonsTile.hidden = counts.reasons_needed === 0;
        reasonsTile.classList.toggle('amber', counts.reasons_complete < counts.reasons_needed);
      }
      const acceptAll = document.querySelector('form[action$="/accept-remaining/"]');
      if (acceptAll) {
        acceptAll.hidden = counts.undecided === 0;
        const label = acceptAll.querySelector('button');
        if (label) label.textContent = `Accept all remaining (${counts.undecided})`;
      }
    }
    if (response.status === 400) {
      const firstError = document.querySelector(`[data-decision-for="${recId}"] .errorlist`);
      firstError?.scrollIntoView({block: 'center'});
    }
  } catch (error) {
    buttons.forEach(b => { b.disabled = false; });
    form.submit();
  }
});
