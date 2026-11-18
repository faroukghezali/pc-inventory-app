/**
 * preparer.js — AI Assistant for PC Refurbishment & Component Swapping
 */

let currentAnalysisData = null;

// ── Open AI Assistant Modal ────────────────────────────────────────────────
async function handleStartPreparation() {
  if (!selectedDbId) {
    alert('Veuillez cocher la case d\'un ordinateur dans le tableau pour lancer la préparation.');
    return;
  }

  const modal = document.getElementById('aiAssistantModal');
  const body  = document.getElementById('aiModalBody');
  if (!modal || !body) return;

  modal.classList.remove('hidden');
  document.body.style.overflow = 'hidden';

  // Step 1: Futuristic Scanning State
  body.innerHTML = `
    <div class="ai-hud-container">
      <div class="ai-telemetry-hud">
        <div class="hud-ring-outer" style="position:absolute;inset:0;border:3px dashed #0284c7;border-radius:50%;"></div>
        <div class="hud-ring-inner" style="position:absolute;inset:10px;border:2px solid #38bdf8;border-top-color:transparent;border-radius:50%;"></div>
        <span class="ai-avatar-core" style="font-size:1.6rem;">🤖</span>
      </div>
      <h3 style="font-size:1.15rem;font-weight:700;color:#0f172a;margin:0 0 0.5rem;">Diagnostic Matriciel en cours…</h3>
      <p style="font-size:0.85rem;color:#64748b;margin:0;">
        Analyse des bus composants et recherche des donneurs compatibles en stock…
      </p>
    </div>
  `;

  try {
    const res = await fetch(`/preparer/analyze/${selectedDbId}`);
    if (!res.ok) throw new Error('Impossible d\'analyser cet ordinateur.');
    const data = await res.json();
    currentAnalysisData = data;
    renderAIAnalysisReport(data);
  } catch (err) {
    body.innerHTML = `
      <div style="text-align:center;padding:2.5rem 1rem;color:#dc2626;">
        <div style="font-size:2.5rem;margin-bottom:0.6rem;">⚠️</div>
        <h3 style="margin:0 0 0.4rem;font-size:1.1rem;font-weight:700;">Échec de l'analyse IA</h3>
        <p style="font-size:0.85rem;color:#64748b;margin:0;">${err.message}</p>
        <button type="button" class="btn btn-secondary" onclick="closeAIModal()" style="margin-top:1.25rem;">
          Fermer
        </button>
      </div>
    `;
  }
}

// ── Render AI Analysis Dialogue & Component Swapping Recommendations ────────
function renderAIAnalysisReport(data) {
  const body = document.getElementById('aiModalBody');
  if (!body) return;

  const target = data.target;
  const components = data.components;
  const totalDefective = data.total_defective;
  const canRepair = data.can_be_repaired;

  let reportHtml = `
    <!-- Top target PC info card -->
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:0.85rem;padding:0.9rem 1.25rem;margin-bottom:1.25rem;display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:0.75rem;">
      <div>
        <span style="font-size:0.7rem;text-transform:uppercase;color:#64748b;font-weight:700;letter-spacing:0.05em;display:block;">Ordinateur sélectionné</span>
        <strong style="font-size:1.05rem;color:#0f172a;">${target.model_name}</strong>
      </div>
      <div style="display:flex;align-items:center;gap:0.85rem;font-size:0.85rem;">
        <span class="font-mono" style="background:#ffffff;border:1px solid #cbd5e1;padding:0.25rem 0.65rem;border-radius:0.4rem;font-weight:600;color:#2563eb;">
          FAN: ${target.fan}
        </span>
        <span class="font-mono" style="background:#ffffff;border:1px solid #cbd5e1;padding:0.25rem 0.65rem;border-radius:0.4rem;color:#334155;">
          SN: ${target.sn}
        </span>
      </div>
    </div>

    <!-- AI Message Bubble -->
    <div style="background:linear-gradient(135deg, #eff6ff 0%, #f0fdf4 100%);border:1px solid #bfdbfe;border-radius:0.85rem;padding:1rem 1.25rem;margin-bottom:1.5rem;display:flex;align-items:flex-start;gap:0.85rem;">
      <span style="font-size:1.6rem;line-height:1;filter:drop-shadow(0 2px 4px rgba(2,132,199,0.3));">🤖</span>
      <div style="font-size:0.875rem;color:#1e293b;line-height:1.5;">
        <strong style="color:#0f172a;display:block;margin-bottom:0.25rem;font-size:0.95rem;">Analyse terminée</strong>
        ${totalDefective === 0 
          ? "Excellente nouvelle ! Tous les composants de cet ordinateur sont <strong style='color:#15803d;'>100% fonctionnels</strong>. Aucun remplacement de pièce n'est nécessaire."
          : `J'ai analysé l'ordinateur et identifié <strong style="color:#dc2626;">${totalDefective} composant(s)</strong> nécessitant un remplacement. J'ai trouvé des composants fonctionnels de remplacement sur d'autres PC du même modèle en stock.`}
      </div>
    </div>

    <h4 style="font-size:0.85rem;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:#475569;margin:0 0 0.85rem;">
      Diagnostic & Recommandations de Remplacement
    </h4>

    <div style="display:flex;flex-direction:column;gap:0.75rem;" id="aiComponentsList">
  `;

  components.forEach(comp => {
    if (!comp.is_defective) {
      // Functional component
      reportHtml += `
        <div class="ai-component-card working-card">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <div style="display:flex;align-items:center;gap:0.6rem;">
              <span style="font-size:1.2rem;">${comp.icon}</span>
              <div>
                <strong style="font-size:0.9rem;color:#0f172a;">${comp.name}</strong>
                <p style="font-size:0.78rem;color:#15803d;margin:0.15rem 0 0;">
                  Fonctionnel — Aucun remplacement requis.
                </p>
              </div>
            </div>
            <span class="indicator-badge indicator-good">✅ Good</span>
          </div>
        </div>
      `;
    } else {
      // Defective component
      const hasDonors = comp.available_donors && comp.available_donors.length > 0;
      const recDonor  = comp.recommended_donor;

      reportHtml += `
        <div class="ai-component-card ${hasDonors ? 'repairable-card' : 'defective-card'}">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:0.5rem;">
            <div style="display:flex;align-items:center;gap:0.6rem;">
              <span style="font-size:1.2rem;">${comp.icon}</span>
              <div>
                <strong style="font-size:0.9rem;color:#0f172a;">${comp.name}</strong>
                <span class="indicator-badge indicator-bad" style="margin-left:0.4rem;font-size:0.7rem;">❌ Défectueux</span>
              </div>
            </div>
          </div>

          ${hasDonors ? `
            <!-- Donor Proposal Box -->
            <div class="ai-donor-box">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.4rem;">
                <span style="font-size:0.75rem;font-weight:700;color:#0369a1;text-transform:uppercase;letter-spacing:0.04em;">
                  Composant donneur trouvé
                </span>
                <span style="font-size:0.75rem;color:#15803d;font-weight:600;">
                  ${comp.key === 'batterie' ? `🔋 ${recDonor.value}% (✅ Bon)` : '✅ État : Oui'}
                </span>
              </div>

              <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.6rem;">
                <div>
                  <span style="font-size:0.85rem;color:#1e293b;font-weight:600;">
                    PC ${recDonor.sn}
                  </span>
                  <span class="font-mono" style="font-size:0.78rem;color:#64748b;margin-left:0.4rem;">
                    (FAN: ${recDonor.fan})
                  </span>
                  <p style="font-size:0.75rem;color:#0284c7;margin:0.2rem 0 0;">
                    Recommandation : Transférer ce composant vers le PC sélectionné.
                  </p>
                </div>

                <!-- Approval Checkbox -->
                <label style="display:inline-flex;align-items:center;gap:0.45rem;cursor:pointer;background:#ffffff;border:1px solid #7dd3fc;padding:0.4rem 0.75rem;border-radius:0.5rem;font-size:0.8rem;font-weight:600;color:#0369a1;">
                  <input type="checkbox" class="ai-transfer-checkbox"
                         data-comp="${comp.key}"
                         data-donor-id="${recDonor.id}"
                         checked
                         onchange="updatePreparationButtonState()">
                  Approuver le transfert
                </label>
              </div>
            </div>
          ` : `
            <div style="margin-top:0.5rem;padding:0.5rem 0.75rem;background:#fee2e2;border-radius:0.5rem;font-size:0.78rem;color:#b91c1c;">
              ⚠️ Aucun composant de remplacement fonctionnel disponible sur les PC en stock de ce modèle.
            </div>
          `}
        </div>
      `;
    }
  });

  reportHtml += `</div>`;

  // Action Footer
  reportHtml += `
    <div style="margin-top:1.5rem;padding-top:1.15rem;border-top:1px solid #e2e8f0;display:flex;justify-content:space-between;align-items:center;gap:0.75rem;flex-wrap:wrap;">
      <button type="button" class="btn btn-ghost" onclick="closeAIModal()">
        Annuler
      </button>

      ${canRepair > 0 ? `
        <button type="button" id="btnValidatePrep" class="btn btn-prepare" onclick="executePreparationProcess()">
          <span style="font-size:1.1rem;">🚀</span>
          Valider la préparation
        </button>
      ` : `
        <button type="button" class="btn btn-secondary" onclick="closeAIModal()">
          Fermer
        </button>
      `}
    </div>
  `;

  body.innerHTML = reportHtml;
  updatePreparationButtonState();
}

function updatePreparationButtonState() {
  const btn = document.getElementById('btnValidatePrep');
  if (!btn) return;
  const checkedBoxes = document.querySelectorAll('.ai-transfer-checkbox:checked');
  btn.disabled = (checkedBoxes.length === 0);
  btn.title = (checkedBoxes.length === 0) 
    ? 'Veuillez approuver au moins un transfert de composant'
    : 'Lancer l\'assemblage et la mise à jour automatique en base de données';
}

// ── Execute Preparation & Futuristic Assembly Animation ─────────────────────
async function executePreparationProcess() {
  const checkedBoxes = document.querySelectorAll('.ai-transfer-checkbox:checked');
  if (checkedBoxes.length === 0) {
    alert('Veuillez approuver au moins un transfert de pièce.');
    return;
  }

  const transfers = {};
  checkedBoxes.forEach(cb => {
    transfers[cb.dataset.comp] = cb.dataset.donorId;
  });

  const body = document.getElementById('aiModalBody');
  if (!body) return;

  // Phase 2: Futuristic Assembly HUD Animation
  body.innerHTML = `
    <div class="ai-hud-container">
      <div class="ai-telemetry-hud">
        <div class="hud-ring-outer" style="position:absolute;inset:0;border:3px dashed #0284c7;border-radius:50%;"></div>
        <div class="hud-ring-inner" style="position:absolute;inset:10px;border:2px solid #10b981;border-top-color:transparent;border-radius:50%;"></div>
        <span class="ai-avatar-core" style="font-size:1.7rem;">⚡</span>
      </div>

      <h3 style="font-size:1.25rem;font-weight:700;color:#0f172a;margin:0 0 0.4rem;">
        Reconditionnement & Assemblage IA en cours…
      </h3>
      <p style="font-size:0.85rem;color:#0284c7;font-weight:600;margin:0 0 1.5rem;">
        Transfert des composants sélectionnés vers le PC cible
      </p>

      <!-- Step-by-Step Diagnostic Logs -->
      <div style="max-width:500px;margin:0 auto 1.5rem;">
        <div class="ai-log-step active" id="step1">
          <span style="font-size:1rem;">⚡</span> [01/05] Initialisation du protocole de reconditionnement IA…
        </div>
        <div class="ai-log-step" id="step2">
          <span style="font-size:1rem;">🔄</span> [02/05] Démontage sécurisé des pièces sur les postes donneurs…
        </div>
        <div class="ai-log-step" id="step3">
          <span style="font-size:1rem;">⚙️</span> [03/05] Intégration et fixation des composants sur le PC cible…
        </div>
        <div class="ai-log-step" id="step4">
          <span style="font-size:1rem;">🔋</span> [04/05] Calibrage énergétique & synchronisation des bus matériels…
        </div>
        <div class="ai-log-step" id="step5">
          <span style="font-size:1rem;">🛡️</span> [05/05] Exécution du diagnostic POST & validation des tests d'intégrité…
        </div>
      </div>

      <!-- Holographic Progress bar -->
      <div style="width:100%;max-width:500px;margin:0 auto;height:8px;background:#e2e8f0;border-radius:999px;overflow:hidden;border:1px solid #cbd5e1;">
        <div id="aiProgressBar" style="width:10%;height:100%;background:linear-gradient(90deg, #0284c7 0%, #10b981 100%);transition:width 0.4s ease;"></div>
      </div>
    </div>
  `;

  // Start API request in parallel
  const apiPromise = fetch('/preparer/execute-transfer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      target_id: currentAnalysisData.target.id,
      transfers: transfers
    })
  });

  // Step-by-step animation sequence (~2.6 seconds)
  const progressBar = document.getElementById('aiProgressBar');

  const setStep = (id, pct, prevId) => {
    if (prevId) {
      const prev = document.getElementById(prevId);
      if (prev) {
        prev.classList.remove('active');
        prev.classList.add('completed');
      }
    }
    const cur = document.getElementById(id);
    if (cur) cur.classList.add('active');
    if (progressBar) progressBar.style.width = pct + '%';
  };

  setTimeout(() => setStep('step2', 35, 'step1'), 500);
  setTimeout(() => setStep('step3', 60, 'step2'), 1100);
  setTimeout(() => setStep('step4', 85, 'step3'), 1700);
  setTimeout(() => setStep('step5', 100, 'step4'), 2300);

  // Wait for both animation & API
  const [res] = await Promise.all([
    apiPromise,
    new Promise(resolve => setTimeout(resolve, 2700))
  ]);

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    body.innerHTML = `
      <div style="text-align:center;padding:2.5rem 1rem;color:#dc2626;">
        <div style="font-size:2.5rem;margin-bottom:0.5rem;">⚠️</div>
        <h3 style="font-size:1.1rem;font-weight:700;margin:0 0 0.35rem;">Erreur lors du transfert</h3>
        <p style="font-size:0.85rem;color:#64748b;margin:0 0 1rem;">${errData.message || 'Une erreur est survenue lors de la mise à jour.'}</p>
        <button type="button" class="btn btn-secondary" onclick="closeAIModal()">Fermer</button>
      </div>
    `;
    return;
  }

  const result = await res.json();

  // Phase 3: Final Assembled Computer Screen & Success Message
  renderPreparationSuccessScreen(result);
}

// ── Phase 3: Final Assembled Computer Screen ────────────────────────────────
function renderPreparationSuccessScreen(result) {
  const body = document.getElementById('aiModalBody');
  if (!body) return;

  const target = result.target;
  const transferred = result.transferred_components || [];

  body.innerHTML = `
    <div style="padding:1.5rem 1.25rem;text-align:center;">
      <!-- Glowing Success Badge -->
      <div class="success-glow-card" style="width:72px;height:72px;border-radius:50%;background:#dcfce7;border:3px solid #10b981;display:flex;align-items:center;justify-content:center;margin:0 auto 1.25rem;font-size:2rem;color:#15803d;">
        ✅
      </div>

      <span style="background:#f0fdf4;color:#15803d;border:1px solid #bbf7d0;padding:0.35rem 0.95rem;border-radius:999px;font-size:0.8rem;font-weight:700;letter-spacing:0.04em;text-transform:uppercase;">
        PC successfully prepared
      </span>

      <h2 style="font-size:1.45rem;font-weight:800;color:#0f172a;margin:0.75rem 0 0.35rem;letter-spacing:-0.02em;">
        PC préparé avec succès !
      </h2>
      <p style="font-size:0.875rem;color:#64748b;margin:0 0 1.5rem;max-width:480px;margin-left:auto;margin-right:auto;">
        Tous les composants validés ont été transférés et mis à jour en base de données. L'ordinateur est opérationnel et prêt au déploiement.
      </p>

      <!-- Transferred Components Log Card -->
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:0.85rem;padding:1rem 1.25rem;text-align:left;margin-bottom:1.25rem;">
        <h4 style="font-size:0.78rem;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:#0369a1;margin:0 0 0.65rem;">
          🔄 Composants transférés & installés
        </h4>
        <ul style="margin:0;padding-left:1.25rem;font-size:0.825rem;color:#334155;line-height:1.6;">
          ${transferred.map(item => `<li><strong>${item}</strong></li>`).join('')}
        </ul>
      </div>

      <!-- Final Assembled PC Hardware State -->
      <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:0.85rem;padding:1.1rem;text-align:left;box-shadow:0 1px 3px rgba(0,0,0,0.05);margin-bottom:1.5rem;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.85rem;padding-bottom:0.5rem;border-bottom:1px solid #f1f5f9;">
          <strong style="color:#0f172a;font-size:0.95rem;">💻 ${target.model_name}</strong>
          <span class="font-mono" style="font-size:0.85rem;color:#2563eb;font-weight:600;">SN: ${target.sn}</span>
        </div>

        <div class="tech-grid">
          <div class="tech-card">
            <span class="tech-card-label">💾 Disque dur</span>
            <div>${renderBoolIndicator(target.disque_dur)}</div>
          </div>
          <div class="tech-card">
            <span class="tech-card-label">🧠 La RAM</span>
            <div>${renderBoolIndicator(target.ram)}</div>
          </div>
          <div class="tech-card">
            <span class="tech-card-label">⌨️ Clavier</span>
            <div>${renderBoolIndicator(target.etat_clavier)}</div>
          </div>
          <div class="tech-card">
            <span class="tech-card-label">📺 Écran</span>
            <div>${renderBoolIndicator(target.etat_ecran)}</div>
          </div>
          <div class="tech-card">
            <span class="tech-card-label">🖥️ Système OS</span>
            <div>${renderBoolIndicator(target.systeme_operateur)}</div>
          </div>
          <div class="tech-card">
            <span class="tech-card-label">🔌 Ports USB</span>
            <div><span style="font-weight:700;color:#1e293b;font-size:0.85rem;">⚡ ${target.ports_usb || 'Toutes'}</span></div>
          </div>
          <div class="tech-card full-width">
            <span class="tech-card-label">🔋 Niveau de Batterie</span>
            <div style="margin-top:0.35rem;">
              ${renderBatteryIndicator(target.batterie)}
            </div>
          </div>
        </div>
      </div>

      <!-- Finish Button -->
      <button type="button" class="btn btn-primary" onclick="finishAndReload()" style="padding:0.75rem 2rem;font-size:0.95rem;">
        ✨ Terminer & Actualiser la liste
      </button>
    </div>
  `;
}

function finishAndReload() {
  closeAIModal();
  window.location.reload();
}

function closeAIModal() {
  const modal = document.getElementById('aiAssistantModal');
  if (modal) modal.classList.add('hidden');
  document.body.style.overflow = '';
}

// ── Event Listener Setup ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const modal = document.getElementById('aiAssistantModal');
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeAIModal();
    });
  }

  // Update prepare button state when row selection changes
  const oldUpdateState = window.updateActionButtonsState;
  window.updateActionButtonsState = function() {
    if (typeof oldUpdateState === 'function') oldUpdateState();
    const btnPrep = document.getElementById('btnPrepareSelected');
    if (btnPrep) {
      btnPrep.disabled = !selectedDbId;
      btnPrep.title = selectedDbId
        ? 'Lancer le diagnostic et la préparation assistée par IA'
        : 'Veuillez sélectionner un PC dans le tableau';
    }
  };

  // Run on load
  if (window.updateActionButtonsState) window.updateActionButtonsState();
});
