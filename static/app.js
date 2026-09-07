document.documentElement.classList.add('js');

const menuButton = document.querySelector('[data-nav-toggle]');
const navigationHeader = document.querySelector('.app-header');
if (menuButton && navigationHeader) {
  menuButton.hidden = false;
  const closeMenu = () => {
    navigationHeader.classList.remove('is-open');
    menuButton.setAttribute('aria-expanded', 'false');
  };
  menuButton.addEventListener('click', () => {
    const open = navigationHeader.classList.toggle('is-open');
    menuButton.setAttribute('aria-expanded', String(open));
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && navigationHeader.classList.contains('is-open')) {
      closeMenu();
      menuButton.focus();
    }
  });
  document.addEventListener('click', event => {
    if (!navigationHeader.contains(event.target)) closeMenu();
  });
}

// Rooms belong to a plant. Clear the old room before changing the workspace.
const planFilters = document.querySelector('[data-plan-filters]');
if (planFilters) {
  const plant = planFilters.querySelector('[name="plant"]');
  const room = planFilters.querySelector('[name="room"]');
  plant?.addEventListener('change', () => {
    room.value = '';
    planFilters.requestSubmit();
  });
  room?.addEventListener('change', () => planFilters.requestSubmit());
}

// Make wide audit tables reachable without a mouse.
document.querySelectorAll('.table-wrap').forEach(wrapper => {
  wrapper.tabIndex = 0;
  wrapper.setAttribute('role', 'region');
  if (!wrapper.hasAttribute('aria-label')) {
    const table = wrapper.querySelector('table');
    const heading = wrapper.previousElementSibling;
    wrapper.setAttribute('aria-label', table?.getAttribute('aria-label') ||
      (heading?.matches('h2, h3') ? heading.textContent : 'Data table'));
  }
});
