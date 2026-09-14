// Capture screen: photo preview and retake, remembered station, the decayed
// count stepper with the doubled-sample prompt, and visible step errors.
// The form carries novalidate so a missed step is explained on screen rather
// than by a browser bubble anchored to a hidden radio.
document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('capture');
  if (!form) return;
  const baseCount = parseInt(form.dataset.fruitCount, 10);
  const doubleCount = parseInt(form.dataset.doubleCount, 10);
  const flagPct = parseFloat(form.dataset.decayFlagPct);

  // Photo: the dashed box is the control. After a shot, show it in place.
  const photo = document.getElementById('photo-input');
  const preview = document.getElementById('photo-preview');
  const box = document.getElementById('photo-box');
  const prompt = box.querySelector('.photo-prompt');
  const retake = document.getElementById('photo-retake');
  let previewUrl;
  photo.addEventListener('change', () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    const has = photo.files && photo.files[0];
    if (has) {
      previewUrl = URL.createObjectURL(photo.files[0]);
      preview.src = previewUrl;
    }
    preview.hidden = !has;
    retake.hidden = !has;
    prompt.hidden = !!has;
    box.classList.toggle('has-photo', !!has);
    clearError(photo.closest('[data-step]'));
  });

  // Station: remember the last choice on this phone.
  const station = document.getElementById('id_calibration');
  if (station) {
    const key = 'lemon-tracker.station';
    try {
      const saved = localStorage.getItem(key);
      if (saved && !station.value && [...station.options].some(o => o.value === saved)) station.value = saved;
    } catch (e) { /* storage unavailable */ }
    station.addEventListener('change', () => {
      try { localStorage.setItem(key, station.value); } catch (e) { /* ignore */ }
    });
  }

  // Decayed-fruit stepper and the doubled-sample prompt.
  const decay = document.getElementById('id_decay_count');
  const note = form.querySelector('[data-tolerance-note]');
  const countLabel = form.querySelector('[data-fruit-count-label]');
  const options = [...form.querySelectorAll('[data-fruit-count-option]')];
  const currentCount = () => {
    const chosen = options.find(o => o.checked);
    return chosen ? parseInt(chosen.value, 10) : baseCount;
  };
  const refresh = () => {
    const total = currentCount();
    decay.max = total;
    if (parseInt(decay.value || '0', 10) > total) decay.value = total;
    countLabel.textContent = total;
    const pct = total ? (100 * parseInt(decay.value || '0', 10)) / total : 0;
    // Ask for the second set only while the base sample is in use.
    note.hidden = !(total === baseCount && parseInt(decay.value || '0', 10) > 0 && pct >= flagPct);
  };
  form.querySelectorAll('[data-step-dir]').forEach(button => {
    button.addEventListener('click', () => {
      const next = parseInt(decay.value || '0', 10) + parseInt(button.dataset.stepDir, 10);
      decay.value = Math.min(Math.max(next, 0), currentCount());
      refresh();
    });
  });
  decay.addEventListener('input', refresh);
  options.forEach(o => o.addEventListener('change', refresh));
  refresh();

  // Visible validation: mark the first incomplete step and scroll to it.
  function clearError(step) {
    if (!step) return;
    step.classList.remove('step-error');
    const text = step.querySelector('[data-step-error]');
    if (text) text.hidden = true;
  }
  form.querySelectorAll('[data-step] input').forEach(input => {
    input.addEventListener('change', () => clearError(input.closest('[data-step]')));
  });
  form.addEventListener('submit', event => {
    let firstBad = null;
    form.querySelectorAll('[data-step]').forEach(step => {
      const name = step.dataset.stepName;
      let ok;
      if (name === 'photo') ok = !!(photo.files && photo.files.length);
      else if (name === 'decay_count') ok = decay.value !== '' && parseInt(decay.value, 10) >= 0 && parseInt(decay.value, 10) <= currentCount();
      else ok = !!step.querySelector(`input[name="${name}"]:checked`);
      if (ok) { clearError(step); return; }
      step.classList.add('step-error');
      const text = step.querySelector('[data-step-error]');
      if (text) text.hidden = false;
      if (!firstBad) firstBad = step;
    });
    if (firstBad) {
      event.preventDefault();
      firstBad.scrollIntoView({behavior: 'smooth', block: 'center'});
      return;
    }
    const button = document.getElementById('save-sample');
    button.disabled = true;
    button.textContent = button.dataset.savingText || button.textContent;
  });
});
