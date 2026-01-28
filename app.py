import os
import sys
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import bleach
import re
from urllib.parse import urlparse
import secrets
import time

# ========================================
# CONFIGURAÇÃO DA APLICAÇÃO
# ========================================

app = Flask(__name__)

# Configurações básicas
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
ADMIN_URL_PREFIX = os.environ.get('ADMIN_URL_PREFIX', '/gestao-exclusiva-netfyber')

# Configuração do banco de dados - SOLUÇÃO DEFINITIVA
DATABASE_URL = os.environ.get('DATABASE_URL')

# Se não houver DATABASE_URL ou se houver erro com PostgreSQL, usar SQLite
if not DATABASE_URL:
    print("⚠️ DATABASE_URL não encontrada, usando SQLite")
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///netfyber.db'
else:
    # Tentar corrigir a URL do PostgreSQL
    try:
        # Converter postgres:// para postgresql://
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        
        # Adicionar parâmetros de conexão segura
        if '?' not in DATABASE_URL:
            DATABASE_URL += '?'
        else:
            DATABASE_URL += '&'
        
        # Parâmetros essenciais para Render
        DATABASE_URL += 'sslmode=require&connect_timeout=10&keepalives=1&keepalives_idle=5&keepalives_interval=2&keepalives_count=2'
        
        app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
        print("✅ Configurado PostgreSQL com SSL")
        
    except Exception as e:
        print(f"⚠️ Erro ao configurar PostgreSQL: {e}")
        print("🔄 Usando SQLite como fallback")
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///netfyber.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 300,
    'pool_pre_ping': True,
    'pool_size': 5,
    'max_overflow': 10,
    'pool_timeout': 30,
}

# Configurações de upload
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads', 'blog')
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8MB

# Configurações Cloudflare R2
app.config['R2_ENABLED'] = os.environ.get('R2_ENABLED', 'false').lower() == 'true'
app.config['R2_ENDPOINT_URL'] = os.environ.get('R2_ENDPOINT_URL', '')
app.config['R2_PUBLIC_URL'] = os.environ.get('R2_PUBLIC_URL', '')
app.config['R2_ACCESS_KEY_ID'] = os.environ.get('R2_ACCESS_KEY_ID', '')
app.config['R2_SECRET_ACCESS_KEY'] = os.environ.get('R2_SECRET_ACCESS_KEY', '')
app.config['R2_BUCKET'] = os.environ.get('R2_BUCKET', 'netfyber-files')

# Extensões permitidas
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

db = SQLAlchemy(app)

# ========================================
# SISTEMA DE AUTENTICAÇÃO
# ========================================

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'
login_manager.login_message = "Por favor, faça login para acessar esta página."
login_manager.login_message_category = "warning"

# ========================================
# MODELOS DO BANCO DE DADOS (SIMPLIFICADOS)
# ========================================

class AdminUser(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), nullable=False, default='admin@netfyber.com')
    password_hash = db.Column(db.String(512), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Configuracao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(100), unique=True, nullable=False)
    valor = db.Column(db.Text, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return AdminUser.query.get(int(user_id))

# ========================================
# FUNÇÕES AUXILIARES
# ========================================

def get_configs():
    """Retorna configurações do site"""
    try:
        configs = {}
        configuracoes = Configuracao.query.all()
        for config in configuracoes:
            configs[config.chave] = config.valor
        return configs
    except Exception as e:
        print(f"⚠️ Erro ao carregar configurações: {e}")
        # Retorna configurações padrão
        return {
            'telefone_contato': '(63) 8494-1778',
            'email_contato': 'contato@netfyber.com',
            'whatsapp_numero': '556384941778',
            'instagram_url': 'https://www.instagram.com/netfybertelecom',
            'hero_imagem': 'images/familia.png',
            'hero_titulo': 'Internet de Alta Velocidade',
            'hero_subtitulo': 'Conecte sua família ao futuro com a NetFyber Telecom',
            'endereco': 'AV. Tocantins – 934, Centro – Sítio Novo – TO',
            'horario_segunda_sexta': '08h às 18h',
            'horario_sabado': '08h às 13h'
        }

def init_database():
    """Inicializa o banco de dados de forma segura"""
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            print(f"🔄 Tentativa {attempt + 1} de {max_retries} para criar tabelas...")
            
            # Criar todas as tabelas
            db.create_all()
            
            # Criar usuário admin se não existir
            admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
            admin_password = os.environ.get('ADMIN_PASSWORD', 'Teste123!')
            
            admin = AdminUser.query.filter_by(username=admin_username).first()
            if not admin:
                admin = AdminUser(username=admin_username)
                admin.set_password(admin_password)
                db.session.add(admin)
                print(f"✅ Admin criado: {admin_username}")
            
            # Criar configurações padrão
            if Configuracao.query.count() == 0:
                configs = [
                    ('telefone_contato', '(63) 8494-1778'),
                    ('email_contato', 'contato@netfyber.com'),
                    ('whatsapp_numero', '556384941778'),
                    ('instagram_url', 'https://www.instagram.com/netfybertelecom'),
                    ('hero_imagem', 'images/familia.png'),
                    ('hero_titulo', 'Internet de Alta Velocidade'),
                    ('hero_subtitulo', 'Conecte sua família ao futuro com a NetFyber Telecom'),
                    ('endereco', 'AV. Tocantins – 934, Centro – Sítio Novo – TO'),
                    ('horario_segunda_sexta', '08h às 18h'),
                    ('horario_sabado', '08h às 13h'),
                ]
                
                for chave, valor in configs:
                    config = Configuracao(chave=chave, valor=valor)
                    db.session.add(config)
                
                print("✅ Configurações padrão criadas")
            
            db.session.commit()
            print("✅ Banco de dados inicializado com sucesso!")
            return True
            
        except Exception as e:
            print(f"❌ Erro na tentativa {attempt + 1}: {e}")
            db.session.rollback()
            
            if attempt < max_retries - 1:
                print(f"⏳ Aguardando {retry_delay} segundos antes da próxima tentativa...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                print("⚠️ Todas as tentativas falharam. O sistema funcionará com configurações padrão.")
                return False
    
    return False

# ========================================
# INICIALIZAÇÃO DO BANCO
# ========================================

# Inicializar banco quando o app iniciar
print("🚀 Inicializando NetFyber Telecom...")
print(f"🔧 Ambiente: {os.environ.get('FLASK_ENV', 'development')}")
print(f"📊 Database URI: {app.config['SQLALCHEMY_DATABASE_URI'][:50]}...")

# Tentar inicializar o banco
with app.app_context():
    try:
        init_database()
    except Exception as e:
        print(f"⚠️ Aviso durante inicialização: {e}")
        # Não quebrar o app se o banco falhar

# ========================================
# ROTAS PÚBLICAS
# ========================================

@app.route('/')
def index():
    return render_template('public/index.html', configs=get_configs())

@app.route('/planos')
def planos():
    return render_template('public/planos.html', configs=get_configs())

@app.route('/blog')
def blog():
    return render_template('public/blog.html', configs=get_configs())

@app.route('/velocimetro')
def velocimetro():
    return render_template('public/velocimetro.html', configs=get_configs())

@app.route('/sobre')
def sobre():
    return render_template('public/sobre.html', configs=get_configs())

# ========================================
# AUTENTICAÇÃO ADMIN
# ========================================

@app.route(f'{ADMIN_URL_PREFIX}/login', methods=['GET', 'POST'])
def admin_login():
    # Verificar se o banco foi inicializado
    try:
        with app.app_context():
            # Verificar se há usuários
            user_count = AdminUser.query.count()
            if user_count == 0:
                # Criar admin padrão
                admin = AdminUser(username='admin')
                admin.set_password('Teste123!')
                db.session.add(admin)
                db.session.commit()
                print("✅ Admin padrão criado automaticamente")
    except Exception as e:
        print(f"⚠️ Verificação do admin: {e}")
    
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        try:
            user = AdminUser.query.filter_by(username=username, is_active=True).first()
            
            if user and user.check_password(password):
                login_user(user, remember=False)
                flash('Login realizado com sucesso!', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Usuário ou senha inválidos.', 'error')
        except Exception as e:
            flash(f'Erro ao fazer login: {str(e)}', 'error')
    
    return render_template('auth/login.html')

@app.route(f'{ADMIN_URL_PREFIX}/logout')
@login_required
def admin_logout():
    logout_user()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('admin_login'))

# ========================================
# DASHBOARD ADMIN
# ========================================

@app.route(f'{ADMIN_URL_PREFIX}/')
@login_required
def admin_dashboard():
    return redirect(url_for('admin_planos'))

@app.route(f'{ADMIN_URL_PREFIX}/planos')
@login_required
def admin_planos():
    return render_template('admin/planos.html')

@app.route(f'{ADMIN_URL_PREFIX}/blog')
@login_required
def admin_blog():
    return render_template('admin/blog.html')

@app.route(f'{ADMIN_URL_PREFIX}/configuracoes', methods=['GET', 'POST'])
@login_required
def admin_configuracoes():
    configs = get_configs()
    return render_template('admin/configuracoes.html', configs=configs)

# ========================================
# ERROS
# ========================================

@app.errorhandler(404)
def pagina_nao_encontrada(error):
    return render_template('public/404.html', configs=get_configs()), 404

@app.errorhandler(500)
def erro_servidor(error):
    return render_template('public/500.html', configs=get_configs()), 500

# ========================================
# PONTO DE ENTRADA
# ========================================

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    
    # Garantir que o diretório de uploads exista
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    app.run(host='0.0.0.0', port=port, debug=debug)