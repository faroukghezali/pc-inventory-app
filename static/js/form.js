/**
 * form.js — Dynamic form field visibility for the Add Computer form.
 * Reads the status <select> and shows/hides the relevant field groups.
 */

const FIELD_RULES = {
  '':                         [],
  'En stock':                 ['model', 'fan', 'sn', 'hw-details', 'obs'],
  'Affecter':                 ['model', 'fan', 'sn', 'username', 'code-user', 'licence', 'obs'],
  'Créé':                     ['model', 'username', 'code-user'],
  'Free':                     ['model', 'quantity'],
  'Utilisation hors domaine': ['model', 'fan', 'sn', 'hw-details', 'obs'],
};

const ALL_FIELDS = [
  'model', 'quantity', 'fan', 'sn',
  'username', 'code-user', 'licence', 'obs',
  'hw-details',
];

function applyStatutVisibility() {
  const statut  = document.getElementById('statutSelect')?.value ?? '';
  const visible = FIELD_RULES[statut] ?? [];

  ALL_FIELDS.forEach(fieldId => {
    const wrapper = document.getElementById('field-' + fieldId);
    if (!wrapper) return;

    const show = visible.includes(fieldId);
    wrapper.classList.toggle('hidden', !show);

    // Animate in when becoming visible
    if (show) {
      wrapper.classList.remove('field-visible');
      void wrapper.offsetWidth; // reflow to restart animation
      wrapper.classList.add('field-visible');
    }

    // Disable hidden inputs so they are never submitted
    wrapper.querySelectorAll('input, select, textarea').forEach(el => {
      el.disabled = !show;
    });
  });
}

// ── Battery slider live label ───────────────────────────────────────────────
function initBatterySlider() {
  const slider = document.getElementById('batterie-slider');
  const label  = document.getElementById('batterie-value');
  if (!slider || !label) return;

  function update() {
    const val = parseInt(slider.value, 10) || 0;
    const isGood = val >= 50;
    const colour = isGood ? '#22c55e' : '#ef4444';
    const tag    = isGood ? '✅ Good' : '❌ Low battery';

    label.textContent = `${val}% — ${tag}`;
    label.style.color = colour;
    slider.style.accentColor = colour;
  }

  slider.addEventListener('input', update);
  update(); // init on page load
}

document.addEventListener('DOMContentLoaded', () => {
  const sel = document.getElementById('statutSelect');
  if (sel) {
    sel.addEventListener('change', applyStatutVisibility);
    applyStatutVisibility(); // restore state on flash-redirect
  }
  initBatterySlider();
});
