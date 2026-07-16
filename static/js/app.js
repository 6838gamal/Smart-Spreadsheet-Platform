/**
 * Smart Spreadsheet Platform — Global JavaScript
 * Utilities and HTMX event handlers.
 */

// ─── HTMX Global Events ────────────────────────────────────────────────────

document.addEventListener('htmx:beforeRequest', (e) => {
  // Disable submit buttons during request
  const form = e.target.closest('form');
  if (form) {
    form.querySelectorAll('button[type=submit]').forEach(btn => {
      btn.disabled = true;
      btn.dataset.originalText = btn.textContent;
    });
  }
});

document.addEventListener('htmx:afterRequest', (e) => {
  // Re-enable submit buttons
  const form = e.target.closest('form');
  if (form) {
    form.querySelectorAll('button[type=submit]').forEach(btn => {
      btn.disabled = false;
      if (btn.dataset.originalText) btn.textContent = btn.dataset.originalText;
    });
  }
});

document.addEventListener('htmx:responseError', (e) => {
  console.error('HTMX request failed:', e.detail.xhr.status, e.detail.xhr.responseText);
});

// ─── File size formatter ────────────────────────────────────────────────────

function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

// ─── Keyboard shortcuts ────────────────────────────────────────────────────

document.addEventListener('keydown', (e) => {
  // Cmd/Ctrl + K → focus search
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault();
    const search = document.querySelector('input[name="search"]');
    if (search) search.focus();
  }
  // Escape → blur any focused input
  if (e.key === 'Escape') {
    document.activeElement?.blur();
  }
});

// ─── Copy to clipboard ────────────────────────────────────────────────────

async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

// ─── Auto-dismiss flash messages ──────────────────────────────────────────

document.querySelectorAll('[data-auto-dismiss]').forEach(el => {
  const delay = parseInt(el.dataset.autoDismiss) || 4000;
  setTimeout(() => el.remove(), delay);
});
