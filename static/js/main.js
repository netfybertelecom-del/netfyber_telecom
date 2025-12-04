// ========================================
// SISTEMA DE COOKIES PROFISSIONAL - CORRIGIDO
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
        if (typeof showNotification === 'function') {
            showNotification(message, type);
        } else {
            console.log(`${type.toUpperCase()}: ${message}`);
        }
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
    }

    disableAnalytics() {
        console.log('📊 Analytics desativado');
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
// SISTEMA DE GEOLOCALIZAÇÃO - CORRIGIDO
// ========================================

class GeolocationManager {
    constructor() {
        this.timeout = 10000;
        this.maxAge = 5 * 60 * 1000;
        this.lastLocation = null;
        this.init();
    }

    init() {
        this.loadCachedLocation();
        
        if (!this.hasLocationPermissionDenied()) {
            setTimeout(() => {
                this.getCurrentLocation().catch(() => {});
            }, 2000);
        }
    }

    hasLocationPermissionDenied() {
        try {
            return localStorage.getItem('location_permission_denied') === 'true';
        } catch {
            return false;
        }
    }

    setLocationPermissionDenied() {
        try {
            localStorage.setItem('location_permission_denied', 'true');
        } catch (error) {
            console.warn('Não foi possível salvar preferência de localização');
        }
    }

    async getCurrentLocation() {
        if (this.lastLocation && (Date.now() - this.lastLocation.timestamp < this.maxAge)) {
            return this.lastLocation;
        }

        return new Promise((resolve, reject) => {
            if (!('geolocation' in navigator)) {
                reject(new Error('Geolocalização não suportada'));
                return;
            }

            const options = {
                enableHighAccuracy: false,
                timeout: this.timeout,
                maximumAge: this.maxAge
            };

            navigator.geolocation.getCurrentPosition(
                async (position) => {
                    try {
                        const location = await this.reverseGeocode(
                            position.coords.latitude,
                            position.coords.longitude
                        );
                        
                        this.lastLocation = {
                            ...location,
                            timestamp: Date.now(),
                            coords: position.coords
                        };
                        
                        this.saveToCache(this.lastLocation);
                        resolve(this.lastLocation);
                        
                    } catch (error) {
                        reject(error);
                    }
                },
                (error) => {
                    const errorMessage = this.getErrorMessage(error);
                    reject(new Error(errorMessage));
                },
                options
            );
        });
    }

    async reverseGeocode(lat, lon) {
        try {
            const response = await fetch(
                `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&accept-language=pt-BR`
            );

            if (!response.ok) throw new Error('Erro na requisição de geocoding');

            const data = await response.json();
            
            return {
                city: data.address.city || data.address.town || data.address.village || 'Cidade desconhecida',
                state: data.address.state || 'Estado desconhecido',
                country: data.address.country || 'País desconhecido',
                displayName: data.display_name || '',
                lat: lat,
                lon: lon
            };
            
        } catch (error) {
            console.warn('Erro no reverse geocoding:', error);
            return {
                city: 'Localização aproximada',
                state: `Lat: ${lat.toFixed(4)}, Lon: ${lon.toFixed(4)}`,
                country: '',
                displayName: '',
                lat: lat,
                lon: lon
            };
        }
    }

    getErrorMessage(error) {
        switch (error.code) {
            case error.PERMISSION_DENIED:
                this.setLocationPermissionDenied();
                return 'Permissão de localização negada.';
            case error.POSITION_UNAVAILABLE:
                return 'Localização indisponível. Verifique sua conexão e GPS.';
            case error.TIMEOUT:
                return 'Tempo de espera esgotado. Tente novamente.';
            default:
                return 'Erro ao obter localização. Tente novamente mais tarde.';
        }
    }

    loadCachedLocation() {
        try {
            const cached = localStorage.getItem('netfyber_location');
            if (cached) {
                const location = JSON.parse(cached);
                if (Date.now() - location.timestamp < this.maxAge) {
                    this.lastLocation = location;
                    this.updateLocationDisplay();
                }
            }
        } catch (error) {
            console.warn('Erro ao carregar localização em cache:', error);
        }
    }

    saveToCache(location) {
        try {
            localStorage.setItem('netfyber_location', JSON.stringify(location));
        } catch (error) {
            console.warn('Erro ao salvar localização em cache:', error);
        }
    }

    updateLocationDisplay() {
        const locationElement = document.getElementById('user-location');
        if (locationElement && this.lastLocation) {
            locationElement.textContent = `${this.lastLocation.city} - ${this.lastLocation.state}`;
            locationElement.classList.remove('text-muted');
            locationElement.classList.add('geolocation-success');
        }
    }

    async requestLocation() {
        try {
            const location = await this.getCurrentLocation();
            this.updateLocationDisplay();
            return location;
        } catch (error) {
            console.warn('Erro na geolocalização:', error);
            const locationElement = document.getElementById('user-location');
            if (locationElement) {
                locationElement.textContent = 'Localização não disponível';
                locationElement.classList.add('geolocation-error');
            }
            throw error;
        }
    }

    async getLocation() {
        return this.requestLocation();
    }
}

// ========================================
// FUNÇÕES FALTANTES - ADICIONADAS
// ========================================

function solicitarLocalizacaoManual() {
    const locationElement = document.getElementById('user-location');
    if (locationElement) {
        locationElement.innerHTML = `
            <button class="btn btn-sm btn-outline-light" onclick="obterLocalizacaoUsuario()">
                <i class="bi bi-geo-alt"></i> Ativar Localização
            </button>
        `;
    }
}

function recusarCookies() {
    if (window.cookieManager && typeof window.cookieManager.acceptEssential === 'function') {
        window.cookieManager.acceptEssential();
    }
}

// ========================================
// SISTEMA DE CARROSSEL PARA PLANOS - CORRIGIDO
// ========================================

class CarrosselPlanos {
    constructor(containerSeletor = '.carrossel-planos-container') {
        this.container = document.querySelector(containerSeletor);
        if (!this.container) return;
        
        this.carrossel = this.container.querySelector('.carrossel-planos');
        this.botaoAnterior = this.container.querySelector('.carrossel-anterior');
        this.botaoProximo = this.container.querySelector('.carrossel-proximo');
        this.indicadoresContainer = this.container.querySelector('.carrossel-indicadores');
        
        this.slides = Array.from(this.carrossel.children);
        this.totalSlides = this.slides.length;
        this.currentIndex = 0;
        this.isDragging = false;
        this.startX = 0;
        this.currentX = 0;
        this.autoPlayInterval = null;
        
        this.init();
    }
    
    init() {
        if (this.totalSlides === 0) return;
        
        this.createIndicators();
        this.updateCarrossel();
        this.addEventListeners();
        this.startAutoPlay();
    }
    
    getSlidesPerView() {
        if (window.innerWidth >= 992) return 3;
        if (window.innerWidth >= 768) return 2;
        return 1;
    }
    
    createIndicators() {
        this.indicadoresContainer.innerHTML = '';
        const slidesPerView = this.getSlidesPerView();
        const totalIndicators = Math.ceil(this.totalSlides / slidesPerView);
        
        for (let i = 0; i < totalIndicators; i++) {
            const indicator = document.createElement('button');
            indicator.className = `carrossel-indicador ${i === 0 ? 'ativo' : ''}`;
            indicator.setAttribute('aria-label', `Ir para grupo de planos ${i + 1}`);
            indicator.addEventListener('click', () => this.goToSlide(i * slidesPerView));
            this.indicadoresContainer.appendChild(indicator);
        }
    }
    
    updateCarrossel() {
        const slidesPerView = this.getSlidesPerView();
        const translateX = -(this.currentIndex * (100 / slidesPerView));
        
        this.carrossel.style.transform = `translateX(${translateX}%)`;
        
        const indicators = this.indicadoresContainer.children;
        const activeIndicator = Math.floor(this.currentIndex / slidesPerView);
        
        for (let i = 0; i < indicators.length; i++) {
            indicators[i].classList.toggle('ativo', i === activeIndicator);
        }
        
        const maxIndex = Math.max(0, this.totalSlides - slidesPerView);
        this.botaoAnterior.disabled = this.currentIndex === 0;
        this.botaoProximo.disabled = this.currentIndex >= maxIndex;
        
        this.carrossel.classList.add('animando');
        setTimeout(() => {
            this.carrossel.classList.remove('animando');
        }, 500);
    }
    
    goToSlide(index) {
        const slidesPerView = this.getSlidesPerView();
        const maxIndex = Math.max(0, this.totalSlides - slidesPerView);
        this.currentIndex = Math.max(0, Math.min(index, maxIndex));
        this.updateCarrossel();
        this.resetAutoPlay();
    }
    
    nextSlide() {
        const slidesPerView = this.getSlidesPerView();
        const maxIndex = Math.max(0, this.totalSlides - slidesPerView);
        
        if (this.currentIndex < maxIndex) {
            this.currentIndex++;
        } else {
            this.currentIndex = 0;
        }
        this.updateCarrossel();
        this.resetAutoPlay();
    }
    
    prevSlide() {
        const slidesPerView = this.getSlidesPerView();
        if (this.currentIndex > 0) {
            this.currentIndex--;
        } else {
            const maxIndex = Math.max(0, this.totalSlides - slidesPerView);
            this.currentIndex = maxIndex;
        }
        this.updateCarrossel();
        this.resetAutoPlay();
    }
    
    addEventListeners() {
        if (this.botaoAnterior) {
            this.botaoAnterior.addEventListener('click', () => this.prevSlide());
        }
        if (this.botaoProximo) {
            this.botaoProximo.addEventListener('click', () => this.nextSlide());
        }
        
        this.addTouchEvents();
        this.addKeyboardEvents();
        
        window.addEventListener('resize', () => this.handleResize());
    }
    
    addTouchEvents() {
        this.carrossel.addEventListener('touchstart', (e) => {
            this.startX = e.touches[0].clientX;
            this.isDragging = true;
            this.carrossel.style.transition = 'none';
        });
        
        this.carrossel.addEventListener('touchmove', (e) => {
            if (!this.isDragging) return;
            this.currentX = e.touches[0].clientX;
            const diff = this.startX - this.currentX;
            const slidesPerView = this.getSlidesPerView();
            const translateX = -(this.currentIndex * (100 / slidesPerView)) - (diff / this.carrossel.offsetWidth) * 100;
            this.carrossel.style.transform = `translateX(${translateX}%)`;
        });
        
        this.carrossel.addEventListener('touchend', () => {
            if (!this.isDragging) return;
            this.isDragging = false;
            this.carrossel.style.transition = 'transform 0.5s cubic-bezier(0.25, 0.46, 0.45, 0.94)';
            
            const diff = this.startX - this.currentX;
            const threshold = 50;
            
            if (diff > threshold) {
                this.nextSlide();
            } else if (diff < -threshold) {
                this.prevSlide();
            } else {
                this.updateCarrossel();
            }
            
            this.resetAutoPlay();
        });
    }
    
    addKeyboardEvents() {
        document.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowLeft') {
                e.preventDefault();
                this.prevSlide();
            }
            if (e.key === 'ArrowRight') {
                e.preventDefault();
                this.nextSlide();
            }
        });
    }
    
    handleResize() {
        this.createIndicators();
        this.updateCarrossel();
    }
    
    startAutoPlay() {
        this.autoPlayInterval = setInterval(() => {
            this.nextSlide();
        }, 8000);
    }
    
    resetAutoPlay() {
        if (this.autoPlayInterval) {
            clearInterval(this.autoPlayInterval);
            this.startAutoPlay();
        }
    }
    
    destroy() {
        if (this.autoPlayInterval) {
            clearInterval(this.autoPlayInterval);
        }
    }
}

// ========================================
// INICIALIZAÇÃO DO CARROSSEL - CORRIGIDA
// ========================================

function initPlanosCarousel() {
    const carrosselContainer = document.querySelector('.carrossel-planos-container');
    if (!carrosselContainer) {
        console.log('❌ Container do carrossel não encontrado');
        return;
    }
    
    try {
        window.planosCarousel = new CarrosselPlanos();
        console.log('✅ Carrossel de planos inicializado');
    } catch (error) {
        console.error('❌ Erro ao inicializar carrossel:', error);
    }
}

// ========================================
// SISTEMA DE HOVER PARA HERO SECTION
// ========================================

function initHeroHover() {
    const heroContainer = document.querySelector('.hero-container');
    const heroContent = document.querySelector('.hero-content');
    
    if (!heroContainer) return;
    
    heroContainer.addEventListener('mouseenter', function() {
        this.classList.add('hero-hover-active');
        if (heroContent) heroContent.style.opacity = '1';
    });
    
    heroContainer.addEventListener('mouseleave', function() {
        this.classList.remove('hero-hover-active');
        if (heroContent) heroContent.style.opacity = '0.7';
    });
}

// ========================================
// SISTEMA DE NOTIFICAÇÕES
// ========================================

function showNotification(message, type = 'info') {
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

// ========================================
// SMOOTH SCROLL
// ========================================

function smoothScroll(target, duration = 1000) {
    const targetElement = document.querySelector(target);
    if (!targetElement) return;
    
    const targetPosition = targetElement.getBoundingClientRect().top + window.pageYOffset;
    const startPosition = window.pageYOffset;
    const distance = targetPosition - startPosition;
    let startTime = null;
    
    function animation(currentTime) {
        if (startTime === null) startTime = currentTime;
        const timeElapsed = currentTime - startTime;
        const run = ease(timeElapsed, startPosition, distance, duration);
        window.scrollTo(0, run);
        if (timeElapsed < duration) requestAnimationFrame(animation);
    }
    
    function ease(t, b, c, d) {
        t /= d / 2;
        if (t < 1) return c / 2 * t * t + b;
        t--;
        return -c / 2 * (t * (t - 2) - 1) + b;
    }
    
    requestAnimationFrame(animation);
}

// ========================================
// LOADING STATES
// ========================================

function setLoadingState(element, isLoading) {
    if (isLoading) {
        element.classList.add('loading');
        element.disabled = true;
        const originalText = element.innerHTML;
        element.innerHTML = `<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Carregando...`;
        element.setAttribute('data-original-text', originalText);
    } else {
        element.classList.remove('loading');
        element.disabled = false;
        const originalText = element.getAttribute('data-original-text');
        if (originalText) {
            element.innerHTML = originalText;
        }
    }
}

// ========================================
// FORM VALIDATION
// ========================================

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
// BLOG FILTERS - CORRIGIDO
// ========================================

function initBlogFilters() {
    const filterButtons = document.querySelectorAll('.filter-btn');
    const blogPosts = document.querySelectorAll('.blog-post-item');
    const filterCount = document.getElementById('filter-count');

    if (filterButtons.length === 0 || blogPosts.length === 0) {
        return;
    }

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
            filterCount.style.opacity = '0.7';
            setTimeout(() => {
                filterCount.style.opacity = '1';
            }, 150);
        }
    }

    function filterPosts(filterValue) {
        let visibleCount = 0;
        
        blogPosts.forEach(post => {
            const postCategory = post.getAttribute('data-category');
            const shouldShow = filterValue === 'all' || postCategory === filterValue;
            
            if (shouldShow) {
                post.style.display = 'block';
                post.classList.remove('hidden');
                visibleCount++;
                
                setTimeout(() => {
                    post.style.opacity = '1';
                    post.style.transform = 'translateY(0)';
                    post.style.visibility = 'visible';
                }, 50);
            } else {
                post.style.opacity = '0';
                post.style.transform = 'translateY(20px)';
                
                setTimeout(() => {
                    post.classList.add('hidden');
                    post.style.display = 'none';
                    post.style.visibility = 'hidden';
                }, 300);
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
            
            const originalHTML = this.innerHTML;
            this.innerHTML = '<i class="bi bi-arrow-repeat bi-spin me-2"></i>Filtrando...';
            
            setTimeout(() => {
                const icon = filterValue === 'all' ? 'bi-grid-3x3-gap' : 
                            filterValue === 'tecnologia' ? 'bi-cpu' : 'bi-newspaper';
                const text = filterValue === 'all' ? 'Todos' : 
                            filterValue === 'tecnologia' ? 'Tecnologia' : 'Notícias';
                this.innerHTML = `<i class="bi ${icon} me-2"></i>${text}`;
                
                filterPosts(filterValue);
            }, 300);
        });
    });

    updateFilterCount('all', blogPosts.length);
}

// ========================================
// SCROLL ANIMATIONS
// ========================================

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

// ========================================
// DEBOUNCE UTILITY
// ========================================

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// ========================================
// FUNÇÕES DE INTERFACE PARA COOKIES
// ========================================

function aceitarTodosCookies() {
    if (window.cookieManager) {
        window.cookieManager.acceptAll();
    }
}

function aceitarCookiesEssenciais() {
    if (window.cookieManager) {
        window.cookieManager.acceptEssential();
    }
}

function aceitarCookies() {
    aceitarTodosCookies();
}

function configurarCookies() {
    const modal = new bootstrap.Modal(document.getElementById('cookieSettingsModal'));
    modal.show();
}

function salvarPreferenciasCookies() {
    const analytics = document.getElementById('cookieAnalytics').checked;
    const personalization = document.getElementById('cookiePersonalization').checked;
    
    if (window.cookieManager) {
        window.cookieManager.customPreferences(analytics, personalization);
    }
    
    const modal = bootstrap.Modal.getInstance(document.getElementById('cookieSettingsModal'));
    if (modal) {
        modal.hide();
    }
}

// ========================================
// FUNÇÕES DE INTERFACE PARA GEOLOCALIZAÇÃO
// ========================================

async function obterLocalizacaoUsuario() {
    try {
        if (!window.geolocationManager) {
            throw new Error('Gerenciador de geolocalização não inicializado');
        }
        await window.geolocationManager.getLocation();
    } catch (error) {
        console.warn('Erro na geolocalização:', error);
        solicitarLocalizacaoManual();
    }
}

// ========================================
// INICIALIZAÇÃO CORRIGIDA E SEGURA
// ========================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 NetFyber - Inicializando sistema...');
    
    try {
        initEssentialSystems();
        initPageSpecificComponents();
        console.log('✅ NetFyber - Sistema inicializado com sucesso!');
    } catch (error) {
        console.error('❌ Erro na inicialização:', error);
        showNotification('Erro na inicialização do sistema. Recarregue a página.', 'danger');
    }
});

function initEssentialSystems() {
    if (typeof CookieManager !== 'undefined') {
        window.cookieManager = new CookieManager();
    }
    
    if (typeof GeolocationManager !== 'undefined') {
        window.geolocationManager = new GeolocationManager();
    }
    
    initSmoothScroll();
    initBootstrapTooltips();
    initScrollAnimations();
}

function initPageSpecificComponents() {
    const path = window.location.pathname;
    
    if (path.includes('/planos') || path === '/') {
        initPlanosCarousel();
    }
    
    if (path.includes('/blog')) {
        initBlogFilters();
    }
    
    if (path === '/') {
        initHeroHover();
    }
    
    initFormValidations();
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

// ========================================
// GLOBAL UTILITIES
// ========================================

window.NetFyberUtils = {
    showNotification,
    smoothScroll,
    validateForm,
    setLoadingState,
    debounce,
    initHeroHover,
    obterLocalizacaoUsuario,
    aceitarTodosCookies,
    aceitarCookiesEssenciais,
    configurarCookies,
    salvarPreferenciasCookies,
    initBlogFilters,
    initPlanosCarousel,
    CarrosselPlanos,
    CookieManager,
    GeolocationManager
};

// ========================================
// ERROR HANDLING
// ========================================

window.addEventListener('error', function(e) {
    console.error('Erro global capturado:', e.error);
    showNotification('Ocorreu um erro inesperado. Tente novamente.', 'danger');
});

window.addEventListener('unhandledrejection', function(e) {
    console.error('Promise rejeitada não tratada:', e.reason);
    showNotification('Erro de carregamento. Verifique sua conexão.', 'warning');
    e.preventDefault();
});