// Animate elements when they come into view
const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('animate');
        }
    });
});

// Observe feature cards
document.querySelectorAll('.feature-card').forEach((card) => {
    observer.observe(card);
});

// GSAP animations
gsap.from(".hero-section h1", {
    duration: 1,
    y: 50,
    opacity: 0,
    ease: "power3.out",
    delay: 0.2
});

gsap.from(".hero-section p", {
    duration: 1,
    y: 30,
    opacity: 0,
    ease: "power3.out",
    delay: 0.4
});

// Form animations
const formGroups = document.querySelectorAll('.form-group');
formGroups.forEach((group, index) => {
    gsap.from(group, {
        duration: 0.5,
        opacity: 0,
        y: 20,
        delay: 0.1 * index,
        ease: "power3.out"
    });
});

// Search functionality
document.addEventListener('DOMContentLoaded', function() {
    // Search Input Handler
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', function(e) {
            const searchTerm = e.target.value.toLowerCase();
            const tableRows = document.querySelectorAll('tbody tr');
            
            tableRows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(searchTerm) ? '' : 'none';
            });
        });
    }

    // Status Filter Handler
    const statusFilter = document.getElementById('statusFilter');
    if (statusFilter) {
        statusFilter.addEventListener('change', function(e) {
            const selectedStatus = e.target.value.toLowerCase();
            const activityCards = document.querySelectorAll('.activity-card');
            
            activityCards.forEach(card => {
                const status = card.querySelector('.badge').textContent.toLowerCase();
                card.style.display = !selectedStatus || status === selectedStatus ? '' : 'none';
            });
        });
    }

    // Form Validation
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!form.checkValidity()) {
                e.preventDefault();
                highlightInvalidFields(form);
            }
        });
    });

    // Alert Close Button
    const closeButtons = document.querySelectorAll('.close-alert');
    closeButtons.forEach(button => {
        button.addEventListener('click', function() {
            this.parentElement.remove();
        });
    });
});

// Highlight invalid fields
function highlightInvalidFields(form) {
    const inputs = form.querySelectorAll('input, select, textarea');
    inputs.forEach(input => {
        if (!input.validity.valid) {
            input.classList.add('invalid');
            showError(input);
        }
    });
}

// Show error messages
function showError(input) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = input.validationMessage;
    input.parentElement.appendChild(errorDiv);
} 