if ('serviceWorker' in navigator) {
   navigator.serviceWorker.register('/sw.js', { scope: '/' }).then(function(reg) {
       // registration worked
       console.log('Registration succeeded. Scope is ' + reg.scope);
   }).catch(function(error) {
       // registration failed
       console.log('Registration failed with ' + error);
   });
}

// Handle PWA install prompt
let deferredPrompt = null;
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;
  const btn = document.getElementById('installPWA');
  if (btn) {
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      try {
        if (deferredPrompt) {
          deferredPrompt.prompt();
          const { outcome } = await deferredPrompt.userChoice;
          console.log('PWA install choice:', outcome);
          deferredPrompt = null;
        } else {
          alert('Чтобы добавить на рабочий стол:\n- Android: Меню браузера → Добавить на главный экран.\n- iOS (Safari): Поделиться → На экран «Домой».');
        }
      } finally {
        btn.disabled = false;
      }
    }, { once: true });
  }
});

window.addEventListener('appinstalled', () => {
  console.log('PWA installed');
  // keep the button visible after install
});
