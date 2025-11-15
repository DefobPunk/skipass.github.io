// Slider functionality
let slideIndex = 0;  // Начинаем с 0, чтобы первый вызов сделал slideIndex = 1
console.log("Slider initialized. slideIndex:", slideIndex);

showSlides();

function showSlides() {
    let slides = document.getElementsByClassName("slide");
    console.log("showSlides called. Number of slides found:", slides.length);
    
    if (slides.length === 0) {
        console.error("No slides found! Check HTML for elements with class 'slide'.");
        return;
    }
    
    // Скрываем все слайды
    for (let i = 0; i < slides.length; i++) {
        slides[i].classList.remove("active");
    }
    
    // Увеличиваем индекс
    slideIndex++;
    console.log("slideIndex after increment:", slideIndex);
    
    // Сбрасываем, если превысили количество слайдов
    if (slideIndex > slides.length) {
        slideIndex = 1;
        console.log("slideIndex reset to:", slideIndex);
    }
    
    // Показываем текущий слайд
    slides[slideIndex - 1].classList.add("active");
    console.log("Active slide index:", slideIndex - 1, "Element:", slides[slideIndex - 1]);
    
    // Повторяем через 5 секунд
    setTimeout(showSlides, 5000);
}

function nextSlide() {
    slideIndex++;
    console.log("nextSlide called. slideIndex:", slideIndex);
    showSlidesManual();
}

function prevSlide() {
    slideIndex--;
    console.log("prevSlide called. slideIndex:", slideIndex);
    showSlidesManual();
}

function showSlidesManual() {
    let slides = document.getElementsByClassName("slide");
    console.log("showSlidesManual called. Number of slides:", slides.length);
    
    if (slides.length === 0) {
        console.error("No slides found!");
        return;
    }
    
    // Сбрасываем индекс, если вышел за границы
    if (slideIndex > slides.length) {
        slideIndex = 1;
    }
    if (slideIndex < 1) {
        slideIndex = slides.length;
    }
    
    // Скрываем все
    for (let i = 0; i < slides.length; i++) {
        slides[i].classList.remove("active");
    }
    
    // Показываем текущий
    slides[slideIndex - 1].classList.add("active");
    console.log("Manual: Active slide index:", slideIndex - 1);
}

// Другие функции (формы)
document.addEventListener("DOMContentLoaded", function() {
    console.log("DOM fully loaded.");
    
    const subscribeForm = document.getElementById("subscribe-form");
    if (subscribeForm) {
        subscribeForm.addEventListener("submit", function(e) {
            e.preventDefault();
            alert("Спасибо за подписку!");
            this.reset();
        });
    }

    const contactForm = document.getElementById("contact-form");
    if (contactForm) {
        contactForm.addEventListener("submit", function(e) {
            e.preventDefault();
            alert("Сообщение отправлено!");
            this.reset();
        });
    }
});
