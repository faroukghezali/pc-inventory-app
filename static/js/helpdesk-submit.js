(() => {
  const form = document.getElementById('helpdeskForm');
  if (!form) return;

  const panel = document.getElementById('helpdeskFormPanel');
  const scanner = document.getElementById('helpdeskScanner');
  const button = form.querySelector('button[type="submit"]');
  const formError = document.getElementById('helpdeskError');
  const scannerError = document.getElementById('scannerError');
  const progressBar = document.getElementById('progressBar');
  const progressTrack = document.getElementById('progressTrack');
  const progressValue = document.getElementById('progressValue');
  const scannerTitle = document.getElementById('scannerTitle');
  const scannerStatus = document.getElementById('scannerStatus');
  const scannerSuccess = document.getElementById('scannerSuccess');

  let submitting = false;
  let progress = 0;
  let animationId = 0;
  let animationGeneration = 0;

  function setProgress(value) {
    progress = Math.min(100, Math.max(0, value));
    progressBar.style.width = `${progress}%`;
    progressTrack.setAttribute('aria-valuenow', String(Math.round(progress)));
    progressValue.textContent = `${Math.round(progress)}%`;
  }

  function animateTo(target, duration) {
    const generation = ++animationGeneration;
    const start = progress;
    const startedAt = performance.now();

    return new Promise((resolve) => {
      function frame(now) {
        if (generation !== animationGeneration) return resolve(false);
        const amount = Math.min(1, (now - startedAt) / duration);
        const eased = 1 - Math.pow(1 - amount, 3);
        setProgress(start + (target - start) * eased);
        if (amount < 1) {
          animationId = requestAnimationFrame(frame);
        } else {
          resolve(true);
        }
      }
      animationId = requestAnimationFrame(frame);
    });
  }

  function restoreForm(message) {
    animationGeneration += 1;
    cancelAnimationFrame(animationId);
    scanner.hidden = true;
    panel.hidden = false;
    formError.textContent = message;
    formError.hidden = false;
    button.disabled = false;
    button.textContent = 'Envoyer la demande';
    submitting = false;
    setProgress(0);
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (submitting) return;
    submitting = true;
    button.disabled = true;
    button.textContent = 'Envoi en cours…';
    formError.hidden = true;
    scannerError.hidden = true;
    scannerSuccess.hidden = true;
    scannerTitle.textContent = 'Analyse de votre demande';
    scannerStatus.textContent = 'Transmission sécurisée en cours…';
    setProgress(0);
    panel.hidden = true;
    scanner.hidden = false;

    const progressPromise = animateTo(88, 2400);
    try {
      const response = await fetch(form.action, {
        method: 'POST',
        body: new FormData(form),
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || !result.ok) {
        restoreForm(result.error || 'Votre demande n’a pas pu être envoyée. Réessayez.');
        return;
      }

      await progressPromise;
      scannerStatus.textContent = 'Demande enregistrée. Finalisation…';
      await animateTo(100, 650);
      scannerTitle.textContent = 'Analyse terminée';
      scannerStatus.hidden = true;
      scannerSuccess.hidden = false;
    } catch (error) {
      restoreForm('Connexion impossible. Vérifiez votre réseau puis réessayez.');
    }
  });
})();
