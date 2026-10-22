// ===== Mobile Menu Toggle =====
const menuToggle = document.querySelector('.menu-toggle');
const mobileMenu = document.querySelector('.mobile-menu');

if (menuToggle && mobileMenu) {
  menuToggle.addEventListener('click', () => {
    const isActive = mobileMenu.classList.toggle('active');
    if (!isActive) {
      // Close keyboard if open
      document.body.blur();
    }
  });
}

// ===== Experience Filters =====
document.addEventListener('DOMContentLoaded', () => {
  const filterButtons = document.querySelectorAll('.filter-btn');
  
  filterButtons.forEach(button => {
    button.addEventListener('click', () => {
      // Remove active class from all buttons
      filterButtons.forEach(btn => btn.classList.remove('active'));
      // Add active class to clicked button
      button.classList.add('active');
      
      // Filter logic (placeholder for actual implementation)
      const category = button.getAttribute('data-category');
      console.log(`Filtering by: ${category}`); // Replace with real filtering
    });
  });
});

// ===== Smooth Scrolling =====
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', function(e) {
    e.preventDefault();
    const target = document.querySelector(this.getAttribute('href'));
    if (target) {
      target.scrollIntoView({
        behavior: 'smooth'
      });
    }
  });
});

// ===== Form Validation (Visit Page) =====
document.addEventListener('DOMContentLoaded', () => {
  const inquiryForm = document.getElementById('inquiry-form');
  if (!inquiryForm) return;

  inquiryForm.addEventListener('submit', (e) => {
    e.preventDefault();
    
    // Basic validation
    const name = document.getElementById('name').value.trim() || '';
    const email = document.getElementById('email').value.trim() || '';
    const message = document.getElementById('message').value.trim() || '';
    
    if (!name || !email || !message) {
      alert('Please fill in all fields.');
      return;
    }

    // Simulate local submission (no actual data sent)
    alert(`Thank you, ${name}! We’ve received your inquiry and will respond within 24 hours.`);
    inquiryForm.reset();
  });
});