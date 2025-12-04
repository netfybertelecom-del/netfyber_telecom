import os
from datetime import timedelta

class Config:
    """Configurações base da aplicação"""
    
    # Configurações básicas do Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'postgresql://postgres:102030@localhost/testenet1')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configurações de segurança
    ADMIN_URL_PREFIX = os.environ.get('ADMIN_URL_PREFIX', '/gestao-exclusiva-netfyber')
    
    # Configurações do Flask-Login
    REMEMBER_COOKIE_DURATION = timedelta(days=1)
    SESSION_PROTECTION = 'strong'
    
    # Configurações de upload (se necessário no futuro)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

class ProductionConfig(Config):
    """Configurações para ambiente de produção"""
    DEBUG = False
    TESTING = False
    
    # Segurança reforçada em produção
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY deve ser definida em produção")
    
    # Em produção, use sempre HTTPS
    PREFERRED_URL_SCHEME = 'https'

class DevelopmentConfig(Config):
    """Configurações para ambiente de desenvolvimento"""
    DEBUG = True
    TESTING = False
    TEMPLATES_AUTO_RELOAD = True
    
    # Para desenvolvimento, permitir mais IPs
    ADMIN_IPS = ['127.0.0.1', 'localhost', '::1', '172.17.0.1']  # Docker

class TestingConfig(Config):
    """Configurações para ambiente de testes"""
    DEBUG = False
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

# Configuração padrão
config = {
    'production': ProductionConfig,
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Retorna a configuração baseada na variável de ambiente FLASK_ENV"""
    env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])