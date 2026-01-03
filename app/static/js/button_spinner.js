document.addEventListener('DOMContentLoaded', function () {
  try {
    const forms = Array.from(document.querySelectorAll('form'));
    const formClickedBtn = new WeakMap();

    forms.forEach(form => {
      if (form.hasAttribute('data-hx-no-spinner')) return;
      // Track which submit button triggered this form submit
      form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(btn => {
        btn.addEventListener('click', function () {
          formClickedBtn.set(form, btn);
        });
      });

      form.addEventListener('submit', function (e) {
        // Do nothing if already handling (avoid double-disable)
        if (form.dataset.hxSubmitting === '1') return;
        form.dataset.hxSubmitting = '1';

        let btn = formClickedBtn.get(form);
        if (!btn) {
          // fallback: first visible, enabled submit button
          btn = Array.from(form.querySelectorAll('button[type="submit"], input[type="submit"]')).find(b => !b.disabled && b.offsetParent !== null) || null;
        }
        if (!btn) return;

        // For input[type=submit], we can't safely set innerHTML; just disable and add spinner sibling
        if (btn.tagName.toLowerCase() === 'input') {
          btn.disabled = true;
          btn.setAttribute('aria-disabled', 'true');
          const spinner = document.createElement('span');
          spinner.className = 'spinner-border spinner-border-sm ms-2 align-middle';
          spinner.setAttribute('role', 'status');
          spinner.setAttribute('aria-hidden', 'true');
          btn.insertAdjacentElement('afterend', spinner);
          return;
        }

        // Preserve width to prevent layout shift
        const rect = btn.getBoundingClientRect();
        const prevWidth = rect.width;
        btn.style.width = prevWidth + 'px';

        // Save original content once
        if (!btn.dataset.originalHtml) {
          btn.dataset.originalHtml = btn.innerHTML;
        }

        // Disable and swap to spinner-only content
        btn.disabled = true;
        btn.setAttribute('aria-disabled', 'true');
        btn.classList.add('disabled');
        btn.innerHTML = '<span class="spinner-border spinner-border-sm align-middle" role="status" aria-hidden="true"></span>';
      }, { capture: true });
    });
  } catch (err) {
    // Fail-safe: never break the page if something goes wrong
    console.error('button_spinner.js error:', err);
  }
});
