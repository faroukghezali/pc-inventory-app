(() => {
  const trigger = document.getElementById('aiAssistantTrigger');
  const overlay = document.getElementById('aiAssistantModal');
  if (!trigger || !overlay) return;

  const closeButton = document.getElementById('aiAssistantClose');
  const scanner = document.getElementById('aiScanner');
  const results = document.getElementById('aiResults');
  const status = document.getElementById('aiScanStatus');
  const progressTrack = document.getElementById('aiProgressTrack');
  const progressBar = document.getElementById('aiProgressBar');
  const progressValue = document.getElementById('aiProgressValue');
  const retryButton = document.getElementById('aiRetry');
  const resultHeadline = document.getElementById('aiResultHeadline');
  const resultSubhead = document.getElementById('aiResultSubhead');
  const resultList = document.getElementById('aiResultsList');
  const updatedAt = document.getElementById('aiUpdatedAt');
  let scanTimer = null;
  let resolveScan = null;
  let pollTimer = null;
  let open = false;
  let lastSignature = '';

  const scanPhases = [
    [0, 'Connexion au registre d’inventaire…'],
    [22, 'Lecture des décharges enregistrées…'],
    [48, 'Vérification des restitutions…'],
    [74, 'Rapprochement des équipements par collaborateur…'],
    [94, 'Préparation de la synthèse…'],
  ];

  function setProgress(value) {
    const progress = Math.min(100, value);
    progressBar.style.width = `${progress}%`;
    progressValue.textContent = `${progress}%`;
    progressTrack.setAttribute('aria-valuenow', String(progress));
    for (const [threshold, label] of scanPhases) {
      if (progress >= threshold) status.textContent = label;
    }
  }

  function animateScan() {
    return new Promise(resolve => {
      resolveScan = resolve;
      let progress = 0;
      setProgress(0);
      scanTimer = window.setInterval(() => {
        progress = Math.min(100, progress + 1);
        setProgress(progress);
        if (progress === 100) {
          window.clearInterval(scanTimer);
          scanTimer = null;
          resolveScan = null;
          status.textContent = 'Analyse terminée.';
          resolve();
        }
      }, 34);
    });
  }

  async function fetchAnalysis() {
    const response = await fetch('/api/ai/inventory-analysis', {
      headers: { Accept: 'application/json' },
      credentials: 'same-origin',
      cache: 'no-store',
    });
    if (!response.ok) throw new Error(`Analyse indisponible (${response.status})`);
    return response.json();
  }

  function addChip(parent, text, kind) {
    const chip = document.createElement('span');
    chip.className = `ai-chip ai-chip-${kind}`;
    chip.textContent = text;
    parent.appendChild(chip);
  }

  function renderAnalysis(data) {
    const employees = Array.isArray(data.employees) ? data.employees : [];
    resultHeadline.textContent = employees.length
      ? `${employees.length} collaborateur${employees.length > 1 ? 's' : ''} à équiper`
      : 'Aucun équipement à compléter';
    resultSubhead.textContent = `${data.employees_scanned || 0} collaborateur${data.employees_scanned === 1 ? '' : 's'} analysé${data.employees_scanned === 1 ? '' : 's'}`;
    resultList.replaceChildren();

    if (!employees.length) {
      const empty = document.createElement('div');
      empty.className = 'ai-empty-state';
      const heading = document.createElement('b');
      heading.textContent = data.employees_scanned ? 'Tout est à jour' : 'Aucun collaborateur à analyser';
      const description = document.createElement('span');
      description.textContent = data.employees_scanned
        ? 'Aucun équipement requis n’a été omis dans les décharges des collaborateurs actifs.'
        : 'Les collaborateurs actifs et leurs mouvements apparaîtront ici dès leur enregistrement.';
      empty.append(heading, description);
      resultList.appendChild(empty);
      return;
    }

    employees.forEach((employee, index) => {
      const card = document.createElement('article');
      card.className = 'ai-employee-card';
      card.style.animationDelay = `${Math.min(index * 45, 270)}ms`;

      const top = document.createElement('div');
      top.className = 'ai-employee-top';
      const name = document.createElement('strong');
      name.textContent = employee.full_name || 'Nom non renseigné';
      top.appendChild(name);
      card.appendChild(top);

      const meta = document.createElement('div');
      meta.className = 'ai-employee-meta';
      [`FAN ${employee.fan || '—'}`, `Code User ${employee.code_user || '—'}`].forEach(value => {
        const item = document.createElement('span');
        item.textContent = value;
        meta.appendChild(item);
      });
      card.appendChild(meta);

      const missingTitle = document.createElement('div');
      missingTitle.className = 'ai-list-caption';
      missingTitle.textContent = 'À remettre · jamais déchargé';
      card.appendChild(missingTitle);
      const missingRow = document.createElement('div');
      missingRow.className = 'ai-chip-row';
      (employee.missing || []).forEach(item => addChip(missingRow, item.label, 'missing'));
      card.appendChild(missingRow);

      if (employee.issued && employee.issued.length) {
        const issuedTitle = document.createElement('div');
        issuedTitle.className = 'ai-list-caption';
        issuedTitle.textContent = 'Historique des équipements remis';
        card.appendChild(issuedTitle);
        const issuedRow = document.createElement('div');
        issuedRow.className = 'ai-chip-row';
        employee.issued.forEach(item => {
          (item.statuses || []).forEach(state => {
            addChip(issuedRow, `${item.label} · ${state}`, state === 'Restitué' ? 'returned' : 'issued');
          });
        });
        if (issuedRow.childElementCount) card.appendChild(issuedRow);
      }

      resultList.appendChild(card);
    });
  }

  function showResults(data) {
    scanner.classList.add('hidden');
    results.classList.remove('hidden');
    renderAnalysis(data);
    updatedAt.textContent = `Actualisé ${new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}`;
    lastSignature = JSON.stringify(data);
  }

  async function runScan() {
    if (scanTimer) window.clearInterval(scanTimer);
    scanner.classList.remove('hidden');
    results.classList.add('hidden');
    retryButton.classList.add('hidden');
    const animation = animateScan();
    try {
      const [data] = await Promise.all([fetchAnalysis(), animation]);
      if (open) showResults(data);
    } catch (error) {
      await animation;
      if (!open) return;
      status.textContent = 'Impossible de lire les mouvements enregistrés. Vérifiez la connexion et réessayez.';
      retryButton.classList.remove('hidden');
    }
  }

  async function refreshIfChanged() {
    if (!open || results.classList.contains('hidden')) return;
    try {
      const data = await fetchAnalysis();
      if (!open) return;
      const signature = JSON.stringify(data);
      if (signature !== lastSignature) showResults(data);
      else updatedAt.textContent = `Actualisé ${new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}`;
    } catch (_) {
      // Keep the last successful scan visible if a background refresh fails.
    }
  }

  function openModal() {
    open = true;
    overlay.classList.remove('hidden');
    overlay.setAttribute('aria-hidden', 'false');
    trigger.setAttribute('aria-expanded', 'true');
    document.body.classList.add('ai-modal-open');
    closeButton.focus();
    runScan();
    pollTimer = window.setInterval(refreshIfChanged, 7000);
  }

  function closeModal() {
    open = false;
    overlay.classList.add('hidden');
    overlay.setAttribute('aria-hidden', 'true');
    trigger.setAttribute('aria-expanded', 'false');
    document.body.classList.remove('ai-modal-open');
    if (scanTimer) window.clearInterval(scanTimer);
    if (resolveScan) resolveScan();
    if (pollTimer) window.clearInterval(pollTimer);
    scanTimer = null;
    resolveScan = null;
    pollTimer = null;
    trigger.focus();
  }

  trigger.addEventListener('click', openModal);
  closeButton.addEventListener('click', closeModal);
  retryButton.addEventListener('click', runScan);
  overlay.addEventListener('click', event => {
    if (event.target === overlay) closeModal();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && open) closeModal();
  });
})();
