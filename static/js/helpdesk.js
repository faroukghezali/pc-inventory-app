document.addEventListener('DOMContentLoaded', () => {
  const track = document.getElementById('helpdeskProgress');
  if (!track) return;
  const bar = document.getElementById('helpdeskProgressBar');
  const value = document.getElementById('helpdeskProgressValue');
  const success = document.getElementById('helpdeskSuccess');
  const copy = document.getElementById('helpdeskScanCopy');
  const started = performance.now();
  const duration = 3200;
  const tick = now => {
    const progress = Math.min(100, Math.round(((now - started) / duration) * 100));
    bar.style.width = `${progress}%`;
    value.textContent = `${progress}%`;
    track.setAttribute('aria-valuenow', progress);
    if (progress < 100) requestAnimationFrame(tick);
    else {
      copy.textContent = 'Your request is now in the IT Helpdesk queue.';
      success.classList.remove('hidden');
      track.setAttribute('aria-label', 'Request received');
    }
  };
  requestAnimationFrame(tick);
});
