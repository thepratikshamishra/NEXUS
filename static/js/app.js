document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll('input[type="date"]').forEach(input => {
    if (!input.value && input.dataset.defaultToday === "true") {
      input.value = new Date().toISOString().slice(0, 10);
    }
  });
  // Dismiss feedback messages automatically after a comfortable reading interval.
  document.querySelectorAll(".flash").forEach((flash) => {
    window.setTimeout(() => {
      if (flash.isConnected) {
        flash.classList.add("flash-out");
        window.setTimeout(() => flash.remove(), 300);
      }
    }, 6500);
  });
});
