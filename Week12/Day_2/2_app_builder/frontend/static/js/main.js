document.addEventListener('DOMContentLoaded', function () {
    // JavaScript setup for TaskMaster Pro initialization.

    // Example: Toggle navigation on mobile
    const navMenu = document.querySelector('.nav-menu');
    const toggleButton = document.querySelector('.hamburger-menu');

    if (toggleButton) {
        toggleButton.addEventListener('click', function () {
            navMenu.classList.toggle('show');
        });
    }

    // Additional interactive features and event listeners

});