/**
 * table.js — Live search, status dropdown filter, row selection & technical details modal.
 */

let selectedDbId = null;
const selectedDbIds = new Set();

// ── Search & Status Filter ──────────────────────────────────────────────────
function filterTable() {
  const textFilter   = document.getElementById('tableSearch')?.value.toLowerCase().trim() ?? '';
  const statusFilter = document.getElementById('statusFilter')?.value.toLowerCase().trim() ?? '';
  const rows         = document.querySelectorAll('#inventoryTable tbody tr[data-db-id]');

  let visibleCount = 0;

  rows.forEach(row => {
    const text   = (row.textContent || row.innerText).toLowerCase();
    const statut = (row.getAttribute('data-statut') || '').toLowerCase();

    const matchesText   = !textFilter || text.includes(textFilter);
    const matchesStatus = !statusFilter || statut === statusFilter;

    const visible = matchesText && matchesStatus;
    row.style.display = visible ? '' : 'none';

    if (visible) visibleCount++;
  });

  // Update visible counter if element exists
  const counter = document.getElementById('filteredCount');
  if (counter) counter.textContent = visibleCount;
}

// ── Row Selection (Checkbox & Row Click) ────────────────────────────────────
function onRowCheckboxChange(checkbox) {
  const row = checkbox.closest('tr');
  if (checkbox.checked) { selectedDbIds.add(checkbox.dataset.dbId); row?.classList.add('row-selected'); }
  else { selectedDbIds.delete(checkbox.dataset.dbId); row?.classList.remove('row-selected'); }
  selectedDbId = selectedDbIds.size === 1 ? [...selectedDbIds][0] : null;
  updateSelectAllState();
  updateActionButtonsState();
}

function toggleSelectAllRows(master) {
  document.querySelectorAll('#inventoryTable tbody .row-select-checkbox').forEach(checkbox => {
    checkbox.checked = master.checked;
    const row = checkbox.closest('tr');
    if (master.checked) selectedDbIds.add(checkbox.dataset.dbId);
    else selectedDbIds.delete(checkbox.dataset.dbId);
    row?.classList.toggle('row-selected', master.checked);
  });
  selectedDbId = selectedDbIds.size === 1 ? [...selectedDbIds][0] : null;
  updateSelectAllState();
  updateActionButtonsState();
}

function updateSelectAllState() {
  const master = document.getElementById('selectAllRows');
  if (!master) return;
  const boxes = [...document.querySelectorAll('#inventoryTable tbody .row-select-checkbox')];
  const checked = boxes.filter(box => box.checked).length;
  master.checked = boxes.length > 0 && checked === boxes.length;
  master.indeterminate = checked > 0 && checked < boxes.length;
}

function exportSelectedRows() {
  const url = new URL('/export/excel', window.location.origin);
  selectedDbIds.forEach(id => url.searchParams.append('ids', id));
  window.location.href = url.toString();
}

function selectRowById(dbId) {
  const cb = document.querySelector(`.row-select-checkbox[data-db-id="${dbId}"]`);
  if (!cb) return;
  cb.checked = !cb.checked;
  onRowCheckboxChange(cb);
}

function updateActionButtonsState() {
  const btnEdit   = document.getElementById('btnEditSelected');
  const btnDelete = document.getElementById('btnDeleteSelected');

  const hasSelection = selectedDbIds.size > 0;

  if (btnEdit) {
    btnEdit.disabled = selectedDbIds.size !== 1;
    btnEdit.title = hasSelection
      ? 'Modifier l\'équipement sélectionné'
      : 'Veuillez sélectionner un équipement dans le tableau';
  }
  if (btnDelete) {
    btnDelete.disabled = !hasSelection;
    btnDelete.title = hasSelection
      ? 'Supprimer l\'équipement sélectionné'
      : 'Veuillez sélectionner un équipement dans le tableau';
  }
}

function handleEditSelected() {
  if (!selectedDbId) {
    alert('Veuillez cocher la case d\'un équipement pour le modifier.');
    return;
  }
  window.location.href = `/edit/${selectedDbId}`;
}

function handleDeleteSelected() {
  if (!selectedDbIds.size) return;
  if (confirm(`Supprimer ${selectedDbIds.size} ordinateur(s) s?lectionn?(s) ? Cette action est irr?versible.`)) {
    const form = document.getElementById('deleteActionForm');
    form.querySelectorAll('input[name="ids"]').forEach(input => input.remove());
    selectedDbIds.forEach(id => { const input = document.createElement('input'); input.type = 'hidden'; input.name = 'ids'; input.value = id; form.appendChild(input); });
    form.submit();
  }
}

// ── Visual Indicators Generator ─────────────────────────────────────────────
function renderBoolIndicator(val) {
  if (!val) {
    return `<span class="indicator-neutral">— Non renseigné</span>`;
  }
  const str = String(val).trim().toLowerCase();
  if (str === 'oui' || str === 'good') {
    return `<span class="indicator-badge indicator-good">✅ Good</span>`;
  }
  if (str === 'non' || str === 'not working') {
    return `<span class="indicator-badge indicator-bad">❌ Not working</span>`;
  }
  return `<span class="indicator-neutral">${val}</span>`;
}

function renderBatteryIndicator(val) {
  if (val === null || val === undefined || val === '') {
    return `<span class="indicator-neutral">— Non renseigné</span>`;
  }
  const num = parseInt(val, 10);
  if (num === 0) return `<span class="indicator-badge indicator-bad">? Batterie absente</span>`;
  if (isNaN(num)) return `<span class="indicator-neutral">${val}</span>`;

  // Condition: Battery below 50% -> ❌ Low battery; 50-100% -> ✅ Good
  const isGood     = num >= 50;
  const badgeClass = isGood ? 'indicator-good' : 'indicator-bad';
  const labelText  = isGood ? '✅ Good' : '❌ Low battery';
  const accentCol  = isGood ? '#16a34a' : '#dc2626';
  const clampPct   = Math.max(0, Math.min(100, num));

  return `
    <div style="display:flex;flex-direction:column;gap:0.4rem;width:100%;">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span style="font-weight:700;font-size:0.95rem;color:${accentCol};">🔋 ${num}%</span>
        <span class="indicator-badge ${badgeClass}">${labelText}</span>
      </div>
      <div style="width:100%;height:8px;background:#e2e8f0;border-radius:999px;overflow:hidden;border:1px solid #cbd5e1;">
        <div style="width:${clampPct}%;height:100%;background:${accentCol};border-radius:999px;transition:width 0.4s ease;"></div>
      </div>
    </div>
  `;
}

function getBadgeClass(statut) {
  if (!statut) return 'badge-default';
  if (statut === 'En stock') return 'badge-en-stock';
  if (statut === 'Utilisation hors domaine') return 'badge-hors';
  if (statut === 'Free') return 'badge-free';
  if (statut === 'Affecter') return 'badge-affecter';
  if (statut === 'Créé') return 'badge-cree';
  return 'badge-default';
}

// ── Details Modal ───────────────────────────────────────────────────────────
async function openDetailsModal(dbId) {
  const modal = document.getElementById('detailsModal');
  const body  = document.getElementById('detailsModalBody');
  const title = document.getElementById('detailsModalTitle');
  if (!modal || !body) return;

  // Show modal immediately with loading state
  modal.classList.remove('hidden');
  document.body.style.overflow = 'hidden'; // prevent bg scroll
  if (title) title.textContent = 'Chargement des détails…';
  body.innerHTML = `
    <div style="text-align:center;padding:2.5rem 1rem;color:var(--text-muted);">
      <div style="font-size:1.8rem;margin-bottom:0.75rem;animation:pulse 1s infinite;">⏳</div>
      <p style="font-size:0.875rem;margin:0;">Récupération des informations techniques…</p>
    </div>
  `;

  try {
    const res = await fetch(`/item/${dbId}/details`);
    if (!res.ok) throw new Error('Équipement non trouvé');
    const data = await res.json();

    if (title) {
      title.innerHTML = `💻 <span style="color:#0f172a;">${data.model_name || 'Ordinateur'}</span>`;
    }

    const badgeCls = getBadgeClass(data.statut);

    body.innerHTML = `
      <!-- Top info bar -->
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:var(--radius-input);padding:0.85rem 1.1rem;margin-bottom:1.25rem;display:flex;flex-wrap:wrap;gap:1rem;justify-content:space-between;align-items:center;">
        <div>
          <span style="font-size:0.7rem;text-transform:uppercase;color:var(--text-muted);display:block;letter-spacing:0.05em;font-weight:600;">Numéro FAN</span>
          <span class="font-mono" style="font-size:0.95rem;font-weight:700;color:#2563eb;">${data.fan || '—'}</span>
        </div>
        <div>
          <span style="font-size:0.7rem;text-transform:uppercase;color:var(--text-muted);display:block;letter-spacing:0.05em;font-weight:600;">Numéro de Série (SN)</span>
          <span class="font-mono" style="font-size:0.9rem;color:#334155;">${data.sn || '—'}</span>
        </div>
        <div>
          <span style="font-size:0.7rem;text-transform:uppercase;color:var(--text-muted);display:block;letter-spacing:0.05em;font-weight:600;">Statut</span>
          <span class="badge ${badgeCls}">${data.statut || 'En stock'}</span>
        </div>
      </div>

      <!-- Technical components grid -->
      <div class="tech-grid">
        <!-- Disque dur -->
        <div class="tech-card">
          <span class="tech-card-label">💾 Disque dur</span>
          <div>${renderBoolIndicator(data.disque_dur)}</div>
        </div>

        <!-- État du clavier -->
        <div class="tech-card">
          <span class="tech-card-label">⌨️ État du clavier</span>
          <div>${renderBoolIndicator(data.etat_clavier)}</div>
        </div>

        <!-- Système opérateur -->
        <div class="tech-card">
          <span class="tech-card-label">🖥️ Système opérateur</span>
          <div>${renderBoolIndicator(data.systeme_operateur)}</div>
        </div>

        <!-- État de l'écran -->
        <div class="tech-card">
          <span class="tech-card-label">📺 État de l'écran</span>
          <div>${renderBoolIndicator(data.etat_ecran)}</div>
        </div>

        <!-- Pav? tactile -->
        <div class="tech-card"><span class="tech-card-label">Pav? tactile</span><div>${renderBoolIndicator(data.pave_tactile)}</div></div>

        <!-- La RAM -->
        <div class="tech-card">
          <span class="tech-card-label">🧠 La RAM</span>
          <div>${renderBoolIndicator(data.ram)}</div>
        </div>

        <!-- Ports USB -->
        <div class="tech-card">
          <span class="tech-card-label">🔌 Ports USB</span>
          <div>
            ${data.ports_usb
              ? `<span style="font-weight:700;color:#1e293b;font-size:0.875rem;">⚡ ${data.ports_usb}</span>`
              : `<span class="indicator-neutral">— Non renseigné</span>`}
          </div>
        </div>

        <!-- Batterie (Full width) -->
        <div class="tech-card full-width">
          <span class="tech-card-label">🔋 Niveau de Batterie</span>
          <div style="margin-top:0.35rem;">
            ${renderBatteryIndicator(data.batterie)}
          </div>
        </div>
      </div>

      <!-- Observations if any -->
      ${data.obs ? `
        <div style="margin-top:1.15rem;background:#f8fafc;border:1px solid #e2e8f0;border-radius:var(--radius-input);padding:0.85rem 1rem;">
          <span class="tech-card-label" style="display:block;margin-bottom:0.25rem;">📝 Observations</span>
          <p style="font-size:0.85rem;color:#334155;margin:0;">${data.obs}</p>
        </div>
      ` : ''}
    `;
  } catch (err) {
    body.innerHTML = `
      <div style="text-align:center;padding:2rem 1rem;color:#dc2626;">
        <div style="font-size:2rem;margin-bottom:0.5rem;">⚠️</div>
        <p style="margin:0;font-weight:600;">Impossible de charger les détails.</p>
        <p style="font-size:0.78rem;color:var(--text-muted);margin-top:0.3rem;">${err.message}</p>
      </div>
    `;
  }
}

function closeDetailsModal() {
  const modal = document.getElementById('detailsModal');
  if (modal) modal.classList.add('hidden');
  document.body.style.overflow = '';
}

// ── Event listeners ─────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const searchInput  = document.getElementById('tableSearch');
  const statusSelect = document.getElementById('statusFilter');

  if (searchInput)  searchInput.addEventListener('keyup', filterTable);
  if (statusSelect) statusSelect.addEventListener('change', filterTable);

  // Close modal when clicking outside dialog
  const modal = document.getElementById('detailsModal');
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeDetailsModal();
    });
  }

  // Close modal on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeDetailsModal();
  });

  // Clicking a row toggles its checkbox
  const rows = document.querySelectorAll('#inventoryTable tbody tr[data-db-id]');
  rows.forEach(row => {
    row.addEventListener('click', (e) => {
      // Ignore if user clicked a button, link, or input directly
      if (e.target.closest('button, a, input, select, form')) return;
      const dbId = row.getAttribute('data-db-id');
      if (dbId) selectRowById(dbId);
    });
  });

  // Initial state check
  updateActionButtonsState();
});
