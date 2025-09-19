if ('serviceWorker' in navigator) {
   navigator.serviceWorker.register('/sw.js', { scope: '/' }).then(function(reg) {
       console.log('Registration succeeded. Scope is ' + reg.scope);
   }).catch(function(error) {
       console.log('Registration failed with ' + error);
   });
}

// Handle PWA install prompt
let deferredPrompt = null;

// Ensure button reference and default hidden state
function getInstallButton() {
  return document.getElementById('installPWA');
}

function showInstallButton() {
  const btn = getInstallButton();
  if (btn) {
    btn.style.display = '';
    btn.disabled = false;
  }
}

function hideInstallButton() {
  const btn = getInstallButton();
  if (btn) {
    btn.style.display = 'none';
  }
}

// Hide button by default until eligible
(function initInstallButtonVisibility() {
  const btn = getInstallButton();
  if (btn) {
    btn.style.display = 'none';
  }
})();

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;
  const btn = getInstallButton();
  if (btn) {
    showInstallButton();
    // Re-bind click each time event fires to use the latest deferredPrompt
    btn.onclick = async () => {
      btn.disabled = true;
      try {
        if (deferredPrompt) {
          deferredPrompt.prompt();
          const { outcome } = await deferredPrompt.userChoice;
          console.log('PWA install choice:', outcome);
          deferredPrompt = null;
          if (outcome === 'accepted') {
            hideInstallButton();
          } else {
            showInstallButton();
          }
        } else {
          alert('Чтобы добавить на рабочий стол:\n- Android: Меню браузера → Добавить на главный экран.\n- iOS (Safari): Поделиться → На экран «Домой».');
        }
      } finally {
        btn.disabled = false;
      }
    };
  }
});

window.addEventListener('appinstalled', () => {
  console.log('PWA installed');
  hideInstallButton();
});
