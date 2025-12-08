// ========================================
// SISTEMA DE COOKIES PROFISSIONAL
// ========================================

class CookieManager {
    constructor() {
        this.cookieName = 'netfyber_cookies';
        this.cookieExpiry = 365;
        this.init();
    }

    init() {
        const preferences = this.getCookiePreferences();
        if (!preferences) {
            setTimeout(() => this.showBanner(), 1500);
        } else {
            this.applyPreferences(preferences);
        }
    }

    getCookiePreferences() {
        try {
            const cookie = localStorage.getItem(this.cookieName);
            return cookie ? JSON.parse(cookie) : null;
        } catch (error) {
            console.warn('Erro ao ler preferências de cookies:', error);
            return null;
        }
    }

    saveCookiePreferences(preferences) {
        try {
            const cookieData = {
                ...preferences,
                timestamp: new Date().toISOString(),
                version: '1.0'
            };
            
            localStorage.setItem(this.cookieName, JSON.stringify(cookieData));
            this.applyPreferences(preferences);
            this.hideBanner();
            this.showConfirmation(preferences);
            
        } catch (error) {
            console.error('Erro ao salvar preferências:', error);
            this.showNotification('Erro ao salvar preferências. Tente novamente.', 'danger');
        }
    }

    showBanner() {
        const banner = document.getElementById('cookie-banner');
        if (banner) {
            banner.style.display = 'block';
            setTimeout(() => {
                banner.classList.add('show');
            }, 100);
        }
    }

    hideBanner() {
        const banner = document.getElementById('cookie-banner');
        if (banner) {
            banner.classList.remove('show');
            setTimeout(() => {
                banner.style.display = 'none';
            }, 300);
        }
    }

    showConfirmation(preferences) {
        const message = preferences.analytics ? 
            'Preferências de cookies salvas com sucesso!' :
            'Cookies essenciais ativados. Sua privacidade é importante para nós.';
        
        this.showNotification(message, 'success');
    }

    showNotification(message, type = 'info') {
        const existingNotification = document.querySelector('.alert.position-fixed');
        if (existingNotification) {
            existingNotification.remove();
        }

        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        notification.style.cssText = `
            top: 20px;
            right: 20px;
            z-index: 9999;
            min-width: 300px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        `;
        
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);
    }

    applyPreferences(preferences) {
        if (preferences.analytics) {
            this.enableAnalytics();
        } else {
            this.disableAnalytics();
        }

        if (preferences.personalization) {
            this.enablePersonalization();
        } else {
            this.disablePersonalization();
        }
    }

    enableAnalytics() {
        console.log('📊 Analytics ativado');
        // Implementar Google Analytics ou similar
    }

    disableAnalytics() {
        console.log('📊 Analytics desativado');
        // Desativar Google Analytics
    }

    enablePersonalization() {
        console.log('🎨 Personalização ativada');
    }

    disablePersonalization() {
        console.log('🎨 Personalização desativada');
    }

    acceptAll() {
        this.saveCookiePreferences({
            essential: true,
            analytics: true,
            personalization: true,
            marketing: false
        });
    }

    acceptEssential() {
        this.saveCookiePreferences({
            essential: true,
            analytics: false,
            personalization: false,
            marketing: false
        });
    }

    customPreferences(analytics, personalization) {
        this.saveCookiePreferences({
            essential: true,
            analytics: analytics,
            personalization: personalization,
            marketing: false
        });
    }

    isAccepted() {
        const prefs = this.getCookiePreferences();
        return prefs !== null;
    }
}

// ========================================
// CARROSSEL DE PLANOS - CLASSE FUNCIONAL
// ========================================

class CarrosselPlanos {
    constructor() {
        this.carrossel = document.querySelector('.carrossel-planos');
        this.container = document.querySelector('.carrossel-planos-container');
        this.items = document.querySelectorAll('.carrossel-item');
        this.btnPrev = document.querySelector('.carrossel-anterior');
        this.btnNext = document.querySelector('.carrossel-proximo');
        this.indicatorsContainer = document.querySelector('.carrossel-indicadores');
        
        if (!this.carrossel || !this.items.length) return;
        
        this.currentIndex = 0;
        this.itemsPerView = this.calculateItemsPerView();
        this.totalSlides = Math.ceil(this.items.length / this.itemsPerView);
        
        this.init();
    }

    calculateItemsPerView() {
        const width = window.innerWidth;
        if (width >= 992) return 4; // Desktop grande
        if (width >= 768) return 2; // Tablet
        return 1; // Mobile
    }

    init() {
        this.createIndicators();
        this.updateCarrossel();
        this.setupEventListeners();
        this.setupResizeListener();
    }

    createIndicators() {
        if (!this.indicatorsContainer) return;
        
        this.indicatorsContainer.innerHTML = '';
        
        for (let i = 0; i < this.totalSlides; i++) {
            const button = document.createElement('button');
            button.className = 'carrossel-indicador';
            button.setAttribute('aria-label', `Ir para slide ${i + 1}`);
            button.addEventListener('click', () => this.goToSlide(i));
            this.indicatorsContainer.appendChild(button);
        }
        
        this.updateIndicators();
    }

    updateIndicators() {
        const indicators = this.indicatorsContainer.querySelectorAll('.carrossel-indicador');
        const activeSlide = Math.floor(this.currentIndex / this.itemsPerView);
        
        indicators.forEach((indicator, index) => {
            if (index === activeSlide) {
                indicator.classList.add('ativo');
            } else {
                indicator.classList.remove('ativo');
            }
        });
    }

    updateCarrossel() {
        const translateX = -this.currentIndex * (100 / this.itemsPerView);
        this.carrossel.style.transform = `translateX(${translateX}%)`;
        
        this.updateIndicators();
        this.updateButtons();
    }

    updateButtons() {
        const isFirstSlide = this.currentIndex === 0;
        const isLastSlide = this.currentIndex >= this.items.length - this.itemsPerView;
        
        if (this.btnPrev) {
            this.btnPrev.disabled = isFirstSlide;
            this.btnPrev.setAttribute('aria-disabled', isFirstSlide);
        }
        
        if (this.btnNext) {
            this.btnNext.disabled = isLastSlide;
            this.btnNext.setAttribute('aria-disabled', isLastSlide);
        }
    }

    next() {
        const maxIndex = this.items.length - this.itemsPerView;
        if (this.currentIndex < maxIndex) {
            this.currentIndex += this.itemsPerView;
            this.updateCarrossel();
        }
    }

    prev() {
        if (this.currentIndex > 0) {
            this.currentIndex -= this.itemsPerView;
            this.updateCarrossel();
        }
    }

    goToSlide(slideIndex) {
        const maxSlide = Math.floor((this.items.length - this.itemsPerView) / this.itemsPerView);
        const targetIndex = Math.min(Math.max(slideIndex, 0), maxSlide) * this.itemsPerView;
        
        if (targetIndex !== this.currentIndex) {
            this.currentIndex = targetIndex;
            this.updateCarrossel();
        }
    }

    setupEventListeners() {
        if (this.btnPrev) {
            this.btnPrev.addEventListener('click', () => this.prev());
        }
        
        if (this.btnNext) {
            this.btnNext.addEventListener('click', () => this.next());
        }
        
        // Suporte a touch/swipe
        let touchStartX = 0;
        let touchEndX = 0;
        
        this.carrossel.addEventListener('touchstart', (e) => {
            touchStartX = e.changedTouches[0].screenX;
        }, { passive: true });
        
        this.carrossel.addEventListener('touchend', (e) => {
            touchEndX = e.changedTouches[0].screenX;
            this.handleSwipe();
        }, { passive: true });
        
        this.carrossel.addEventListener('mousedown', (e) => {
            touchStartX = e.screenX;
        });
        
        this.carrossel.addEventListener('mouseup', (e) => {
            touchEndX = e.screenX;
            this.handleSwipe();
        });
    }

    handleSwipe() {
        const swipeThreshold = 50;
        const diff = touchStartX - touchEndX;
        
        if (Math.abs(diff) > swipeThreshold) {
            if (diff > 0) {
                this.next();
            } else {
                this.prev();
            }
        }
    }

    setupResizeListener() {
        let resizeTimeout;
        
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimeout);
            
            resizeTimeout = setTimeout(() => {
                const newItemsPerView = this.calculateItemsPerView();
                
                if (newItemsPerView !== this.itemsPerView) {
                    this.itemsPerView = newItemsPerView;
                    this.totalSlides = Math.ceil(this.items.length / this.itemsPerView);
                    this.createIndicators();
                    this.currentIndex = Math.min(this.currentIndex, this.items.length - this.itemsPerView);
                    this.updateCarrossel();
                }
            }, 250);
        });
    }
}

// ========================================
// INICIALIZAÇÃO CORRIGIDA
// ========================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 NetFyber - Inicializando sistema...');
    
    try {
        initEssentialSystems();
        initPageSpecificComponents();
        console.log('✅ NetFyber - Sistema inicializado com sucesso!');
    } catch (error) {
        console.error('❌ Erro na inicialização:', error);
    }
});

function initEssentialSystems() {
    // Inicializar Cookie Manager
    window.cookieManager = new CookieManager();
    
    // Inicializar componentes básicos
    initSmoothScroll();
    initBootstrapTooltips();
    initScrollAnimations();
    initFormValidations();
}

function initPageSpecificComponents() {
    const path = window.location.pathname;
    
    // Inicializar carrossel de planos se estiver na página de planos
    if (path.includes('/planos') || path === '/') {
        initPlanosCarousel();
    }
    
    // Inicializar filtros do blog se estiver na página do blog
    if (path.includes('/blog')) {
        initBlogFilters();
    }
}

function initPlanosCarousel() {
    const carrosselContainer = document.querySelector('.carrossel-planos-container');
    if (!carrosselContainer) return;
    
    try {
        window.planosCarousel = new CarrosselPlanos();
        console.log('✅ Carrossel de planos inicializado');
    } catch (error) {
        console.error('❌ Erro ao inicializar carrossel:', error);
    }
}

function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href !== '#' && href !== '') {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    target.scrollIntoView({ 
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            }
        });
    });
}

function initBootstrapTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

function initScrollAnimations() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('fade-in-up');
                observer.unobserve(entry.target);
            }
        });
    }, { 
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    });
    
    const elementsToAnimate = document.querySelectorAll('.feature-card, .plan-card, .blog-post-item, .guia-card');
    elementsToAnimate.forEach(el => {
        observer.observe(el);
    });
}

function initFormValidations() {
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!validateForm(this)) {
                e.preventDefault();
                const firstInvalid = this.querySelector('.is-invalid');
                if (firstInvalid) {
                    firstInvalid.scrollIntoView({ 
                        behavior: 'smooth', 
                        block: 'center' 
                    });
                    firstInvalid.focus();
                }
            }
        });
    });
}

function validateForm(form) {
    const inputs = form.querySelectorAll('input[required], textarea[required], select[required]');
    let isValid = true;
    
    inputs.forEach(input => {
        if (!input.value.trim()) {
            input.classList.add('is-invalid');
            isValid = false;
            
            if (!input.nextElementSibling || !input.nextElementSibling.classList.contains('invalid-feedback')) {
                const errorDiv = document.createElement('div');
                errorDiv.className = 'invalid-feedback';
                errorDiv.textContent = 'Este campo é obrigatório.';
                input.parentNode.appendChild(errorDiv);
            }
        } else {
            input.classList.remove('is-invalid');
            const errorDiv = input.nextElementSibling;
            if (errorDiv && errorDiv.classList.contains('invalid-feedback')) {
                errorDiv.remove();
            }
        }
    });
    
    return isValid;
}

// ========================================
// FILTROS DO BLOG
// ========================================

function initBlogFilters() {
    const filterButtons = document.querySelectorAll('.filter-btn');
    const blogPosts = document.querySelectorAll('.blog-post-item');
    const filterCount = document.getElementById('filter-count');

    if (filterButtons.length === 0 || blogPosts.length === 0) return;

    function updateFilterCount(filter, count) {
        let message = '';
        
        switch(filter) {
            case 'all':
                message = `Mostrando todos os ${count} posts`;
                break;
            case 'tecnologia':
                message = `${count} post${count !== 1 ? 's' : ''} de tecnologia`;
                break;
            case 'noticias':
                message = `${count} post${count !== 1 ? 's' : ''} de notícias`;
                break;
        }
        
        if (filterCount) {
            filterCount.textContent = message;
        }
    }

    function filterPosts(filterValue) {
        let visibleCount = 0;
        
        blogPosts.forEach(post => {
            const postCategory = post.getAttribute('data-category');
            const shouldShow = filterValue === 'all' || postCategory === filterValue;
            
            if (shouldShow) {
                post.classList.remove('hidden');
                visibleCount++;
            } else {
                post.classList.add('hidden');
            }
        });
        
        updateFilterCount(filterValue, visibleCount);
    }

    filterButtons.forEach(button => {
        button.addEventListener('click', function() {
            filterButtons.forEach(btn => {
                btn.classList.remove('active', 'btn-primary');
                btn.classList.add('btn-outline-primary');
            });
            
            this.classList.remove('btn-outline-primary');
            this.classList.add('active', 'btn-primary');
            
            const filterValue = this.getAttribute('data-filter');
            filterPosts(filterValue);
        });
    });

    updateFilterCount('all', blogPosts.length);
}

// ========================================
// FUNÇÕES GLOBAIS PARA COOKIES
// ========================================

function aceitarTodosCookies() {
    if (window.cookieManager) {
        window.cookieManager.acceptAll();
    }
}

function configurarCookies() {
    const modal = new bootstrap.Modal(document.getElementById('cookieSettingsModal'));
    modal.show();
}

function salvarPreferenciasCookies() {
    const analytics = document.getElementById('cookieAnalytics')?.checked || false;
    const personalization = document.getElementById('cookiePersonalization')?.checked || false;
    
    if (window.cookieManager) {
        window.cookieManager.customPreferences(analytics, personalization);
    }
    
    const modal = bootstrap.Modal.getInstance(document.getElementById('cookieSettingsModal'));
    if (modal) {
        modal.hide();
    }
}

function aceitarCookies() {
    aceitarTodosCookies();
}

// ========================================
// EXPORTAR FUNÇÕES GLOBAIS
// ========================================

window.NetFyberUtils = {
    CookieManager,
    CarrosselPlanos,
    initBlogFilters,
    initPlanosCarousel
};

// ========================================
// HANDLING DE ERROS
// ========================================

window.addEventListener('error', function(e) {
    console.error('Erro global capturado:', e.error);
});

window.addEventListener('unhandledrejection', function(e) {
    console.error('Promise rejeitada não tratada:', e.reason);
    e.preventDefault();
});