window.addEventListener("DOMContentLoaded", () => {
  const box = document.querySelector(".login-box, .register-box");
  if (box) {
    // ensures the initial state is applied first
    requestAnimationFrame(() => box.classList.add("card-show"));
  }
});