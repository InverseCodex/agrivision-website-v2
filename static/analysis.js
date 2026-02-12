const toggleBtn = document.querySelector(".image-header-toggle-button");
let circlePointer = document.querySelector(".circle-toggle");

toggleBtn.addEventListener('click', () => {
    circlePointer.classList.toggle("inactive-circle");
    toggleBtn.classList.toggle("image-toggle-active");
})