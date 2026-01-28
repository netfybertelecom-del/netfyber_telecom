"""
NetFyber Telecom - App Principal
Configurado para Render.com com PostgreSQL SSL
"""

import os
import sys
import uuid
import bleach
import secrets
import re
from urllib.parse import urlparse
from datetime import datetime, timedelta

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# ========================================
# CONFIGURAÇÃO INICIAL
# ========================================

app = Flask(__name__)

# CONFIGURAÇÕES CRÍTICAS - OBRIGATÓRIAS PARA RENDER
# ==================================================

# 1. SECRET_KEY - Usa variável do Render ou gera uma
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# 2. DATABASE_URL - CORREÇÃO COMPLETA PARA SSL
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    print("ERRO CRÍTICO: DATABASE_URL não configurada!")
    sys.exit(1)

# Converter postgres:// para postgresql:// (necessário para SQLAlchemy)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# ADICIONAR SSL OBRIGATÓRIO PARA RENDER
if DATABASE_URL.startswith("postgresql://"):
    # Verificar se já tem parâmetros
    if '?' in DATABASE_URL:
        # Verificar se já tem sslmode
        if 'sslmode=' not in DATABASE_URL:
            DATABASE_URL += '&sslmode=require'
    else:
        DATABASE_URL += '?sslmode=require'
    
    # Adicionar configurações extras de SSL
    if 'sslmode=require' in DATABASE_URL:
        DATABASE_URL += '&sslrootcert=system'

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 300,
    'pool_pre_ping': True,
    'pool_size': 5,
    'max_overflow': 10,
    'pool_timeout': 30,
    'connect_args': {
        'connect_timeout': 10,
        'keepalives_idle': 30,
        'keepalives_interval': 10,
        'keepalives_count': 5,
        'sslmode': 'require'
    }
}

# 3. CONFIGURAÇÕES ADMIN - USAR DO RENDER
ADMIN_URL_PREFIX = os.environ.get('ADMIN_URL_PREFIX', '/gestao-exclusiva-netfyber')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# 4. CONFIGURAÇÕES DE UPLOAD
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads', 'blog')
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8MB
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Inicializar extensões
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'
login_manager.login_message = "Por favor, faça login para acessar esta área."
login_manager.login_message_category = "warning"

# ========================================
# MODELOS DO BANCO DE DADOS
# ========================================

class AdminUser(UserMixin, db.Model):
    __tablename__ = 'admin_users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(512), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def update_login_info(self):
        self.last_login = datetime.utcnow()
        db.session.commit()

class Configuracao(db.Model):
    __tablename__ = 'configuracoes'
    
    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(100), unique=True, nullable=False)
    valor = db.Column(db.Text, nullable=False)
    descricao = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Plano(db.Model):
    __tablename__ = 'planos'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    preco = db.Column(db.String(20), nullable=False)
    velocidade = db.Column(db.String(50))
    features = db.Column(db.Text, nullable=False)
    recomendado = db.Column(db.Boolean, default=False)
    ordem_exibicao = db.Column(db.Integer, default=0)
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def get_features_list(self):
        if not self.features:
            return []
        return [f.strip() for f in self.features.split('\n') if f.strip()]

class Post(db.Model):
    __tablename__ = 'posts'
    
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    conteudo = db.Column(db.Text, nullable=False)
    resumo = db.Column(db.Text, nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    imagem = db.Column(db.String(500), default='default.jpg')
    link_materia = db.Column(db.String(500), nullable=False)
    data_publicacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def get_conteudo_html(self):
        if not self.conteudo:
            return ""
        
        content = self.conteudo
        content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
        content = re.sub(r'\*(.*?)\*', r'<em>\1</em>', content)
        content = content.replace('\n', '<br>')
        
        allowed_tags = ['p', 'br', 'strong', 'em', 'b', 'i', 'u', 'a', 
                       'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'blockquote']
        allowed_attrs = {'a': ['href', 'target', 'rel', 'title']}
        
        sanitized = bleach.clean(content, tags=allowed_tags, attributes=allowed_attrs, strip=True)
        
        def add_link_attributes(attrs, new):
            href = attrs.get((None, 'href'), '')
            if href and href.startswith(('http://', 'https://')):
                attrs[(None, 'target')] = '_blank'
                attrs[(None, 'rel')] = 'noopener noreferrer'
            return attrs
        
        return bleach.linkify(sanitized, callbacks=[add_link_attributes])
    
    def get_data_formatada(self):
        return self.data_publicacao.strftime('%d/%m/%Y')
    
    def get_imagem_url(self):
        if not self.imagem or self.imagem == 'default.jpg':
            return '/static/images/blog/default.jpg'
        return f'/static/uploads/blog/{self.imagem}'

# ========================================
# INICIALIZAÇÃO DO BANCO
# ========================================

@login_manager.user_loader
def load_user(user_id):
    try:
        return AdminUser.query.get(int(user_id))
    except:
        return None

def get_configs():
    try:
        configs = {}
        for config in Configuracao.query.all():
            configs[config.chave] = config.valor
        return configs
    except Exception as e:
        print(f"Erro ao carregar configurações: {e}")
        return {}

def sanitize_input(text):
    if not text:
        return ""
    return bleach.clean(text.strip(), tags=[], attributes={}, strip=True)

# Variável para controlar inicialização
_db_initialized = False

def initialize_database():
    """Inicializa o banco de dados com dados padrão"""
    global _db_initialized
    
    if _db_initialized:
        return
    
    try:
        print("🚀 Inicializando banco de dados...")
        
        # Criar tabelas se não existirem
        db.create_all()
        print("✅ Tabelas criadas/verificadas")
        
        # CRIAR USUÁRIO ADMIN A PARTIR DAS VARIÁVEIS DO RENDER
        admin_username = os.environ.get('ADMIN_USERNAME')
        admin_password = os.environ.get('ADMIN_PASSWORD')
        admin_email = os.environ.get('ADMIN_EMAIL')
        
        if admin_username and admin_password:
            # Verificar se usuário já existe
            existing_admin = AdminUser.query.filter_by(username=admin_username).first()
            
            if not existing_admin:
                print(f"👤 Criando usuário admin: {admin_username}")
                admin = AdminUser(
                    username=admin_username,
                    email=admin_email if admin_email else f"{admin_username}@netfyber.com",
                    is_active=True
                )
                admin.set_password(admin_password)
                db.session.add(admin)
                print(f"✅ Usuário admin criado: {admin_username}")
            else:
                print(f"ℹ️ Usuário admin já existe: {admin_username}")
                # Atualizar senha se necessário
                if admin_password and not existing_admin.check_password(admin_password):
                    existing_admin.set_password(admin_password)
                    print(f"🔑 Senha do admin atualizada")
        else:
            print("⚠️ Variáveis ADMIN_USERNAME ou ADMIN_PASSWORD não configuradas no Render")
            print(f"   ADMIN_USERNAME: {'[CONFIGURADO]' if admin_username else '[FALTANDO]'}")
            print(f"   ADMIN_PASSWORD: {'[CONFIGURADO]' if admin_password else '[FALTANDO]'}")
        
        # Criar configurações padrão se não existirem
        if Configuracao.query.count() == 0:
            print("⚙️ Criando configurações padrão...")
            configs = [
                ('telefone_contato', '(63) 8494-1778', 'Telefone de contato'),
                ('email_contato', 'contato@netfyber.com', 'Email de contato'),
                ('endereco', 'AV. Tocantins – 934, Centro – Sítio Novo – TO', 'Endereço da empresa'),
                ('horario_segunda_sexta', '08h às 18h', 'Horário de atendimento'),
                ('horario_sabado', '08h às 13h', 'Horário de sábado'),
                ('whatsapp_numero', '556384941778', 'Número do WhatsApp'),
                ('instagram_url', 'https://www.instagram.com/netfybertelecom', 'URL do Instagram'),
                ('hero_imagem', 'images/familia.png', 'Imagem do hero'),
                ('hero_titulo', 'Internet de Alta Velocidade', 'Título principal'),
                ('hero_subtitulo', 'Conecte sua família ao futuro com a NetFyber Telecom', 'Subtítulo'),
            ]
            
            for chave, valor, descricao in configs:
                config = Configuracao(chave=chave, valor=valor, descricao=descricao)
                db.session.add(config)
            print("✅ Configurações padrão criadas")
        
        # Criar planos padrão se não existirem
        if Plano.query.count() == 0:
            print("📊 Criando planos padrão...")
            planos = [
                Plano(nome='100 MEGA', preco='89,90', velocidade='100 Mbps', 
                      features='Wi-Fi Grátis\nInstalação Grátis\nSuporte 24h\nFibra Óptica'),
                Plano(nome='200 MEGA', preco='99,90', velocidade='200 Mbps', 
                      features='Wi-Fi Grátis\nInstalação Grátis\nSuporte 24h\nFibra Óptica\nModem Incluso'),
                Plano(nome='400 MEGA', preco='119,90', velocidade='400 Mbps', 
                      features='Wi-Fi Grátis\nInstalação Grátis\nSuporte 24h\nFibra Óptica\nModem Incluso\nAntivírus'),
            ]
            
            for plano in planos:
                db.session.add(plano)
            print("✅ Planos padrão criados")
        
        db.session.commit()
        _db_initialized = True
        print("🎉 Banco de dados inicializado com sucesso!")
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ ERRO CRÍTICO ao inicializar banco: {e}")
        import traceback
        traceback.print_exc()
        # Não levantamos a exceção para permitir que o app tente carregar sem o banco

# Middleware para inicializar antes do primeiro request
@app.before_request
def before_request_handler():
    """Executa antes de cada request para garantir banco inicializado"""
    try:
        if not _db_initialized:
            initialize_database()
    except Exception as e:
        print(f"⚠️ Aviso na inicialização: {e}")

# ========================================
# ROTAS PÚBLICAS
# ========================================

@app.route('/')
def index():
    return render_template('public/index.html', configs=get_configs())

@app.route('/planos')
def planos():
    try:
        planos_data = Plano.query.filter_by(ativo=True).order_by(Plano.ordem_exibicao).all()
    except Exception as e:
        print(f"Erro ao carregar planos: {e}")
        planos_data = []
    return render_template('public/planos.html', planos=planos_data, configs=get_configs())

@app.route('/blog')
def blog():
    try:
        posts = Post.query.filter_by(ativo=True).order_by(Post.data_publicacao.desc()).all()
    except Exception as e:
        print(f"Erro ao carregar posts: {e}")
        posts = []
    return render_template('public/blog.html', configs=get_configs(), posts=posts)

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
    if current_user.is_authenticated:
        return redirect(url_for('admin_planos'))
    
    if request.method == 'POST':
        username = sanitize_input(request.form.get('username', ''))
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Preencha todos os campos.', 'error')
            return render_template('auth/login.html')
        
        try:
            user = AdminUser.query.filter_by(username=username, is_active=True).first()
            
            if user and user.check_password(password):
                login_user(user, remember=False)
                user.update_login_info()
                flash(f'Bem-vindo, {user.username}!', 'success')
                return redirect(url_for('admin_planos'))
            else:
                flash('Credenciais inválidas. Verifique o usuário e senha.', 'error')
                
        except Exception as e:
            flash(f'Erro no servidor: {str(e)}', 'error')
            print(f"Erro no login: {e}")
    
    return render_template('auth/login.html')

@app.route(f'{ADMIN_URL_PREFIX}/logout')
@login_required
def admin_logout():
    logout_user()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('admin_login'))

# ========================================
# ROTAS ADMINISTRATIVAS
# ========================================

@app.route(f'{ADMIN_URL_PREFIX}/planos')
@login_required
def admin_planos():
    try:
        planos_data = Plano.query.filter_by(ativo=True).order_by(Plano.ordem_exibicao).all()
    except Exception as e:
        print(f"Erro ao carregar planos: {e}")
        planos_data = []
        flash('Erro ao carregar planos.', 'error')
    return render_template('admin/planos.html', planos=planos_data)

@app.route(f'{ADMIN_URL_PREFIX}/blog')
@login_required
def admin_blog():
    try:
        posts = Post.query.filter_by(ativo=True).order_by(Post.data_publicacao.desc()).all()
    except Exception as e:
        print(f"Erro ao carregar posts: {e}")
        posts = []
        flash('Erro ao carregar posts.', 'error')
    return render_template('admin/blog.html', posts=posts)

@app.route(f'{ADMIN_URL_PREFIX}/configuracoes', methods=['GET', 'POST'])
@login_required
def admin_configuracoes():
    if request.method == 'POST':
        try:
            for chave, valor in request.form.items():
                if chave not in ['csrf_token', 'submit'] and valor.strip():
                    config = Configuracao.query.filter_by(chave=chave).first()
                    if config:
                        config.valor = sanitize_input(valor)
                    else:
                        config = Configuracao(chave=chave, valor=sanitize_input(valor))
                        db.session.add(config)
            db.session.commit()
            flash('Configurações salvas!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {str(e)}', 'error')
    
    return render_template('admin/configuracoes.html', configs=get_configs())

# ========================================
# UTILITÁRIOS
# ========================================

@app.route('/health')
def health_check():
    try:
        # Testar conexão com banco
        db.session.execute('SELECT 1')
        db_status = 'healthy'
    except Exception as e:
        db_status = f'error: {str(e)}'
    
    return jsonify({
        'status': 'ok',
        'database': db_status,
        'initialized': _db_initialized,
        'timestamp': datetime.utcnow().isoformat()
    })

@app.errorhandler(404)
def pagina_nao_encontrada(error):
    return render_template('public/404.html', configs=get_configs()), 404

@app.errorhandler(403)
def acesso_negado(error):
    return render_template('public/403.html', configs=get_configs()), 403

@app.errorhandler(500)
def erro_servidor(error):
    return render_template('public/500.html', configs=get_configs()), 500

# ========================================
# INICIALIZAÇÃO DA APLICAÇÃO
# ========================================

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get('FLASK_ENV') != 'production'
    
    # Criar diretórios necessários
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs('static/images/blog', exist_ok=True)
    
    # Log inicial
    print("=" * 60)
    print("🚀 NETFYBER TELECOM - INICIANDO")
    print("=" * 60)
    print(f"🔧 Ambiente: {os.environ.get('FLASK_ENV', 'development')}")
    print(f"📊 Banco: {DATABASE_URL[:50]}...")
    print(f"🔐 SSL: {'SIM (sslmode=require)' if 'sslmode=require' in DATABASE_URL else 'NÃO'}")
    print(f"👤 Admin: {os.environ.get('ADMIN_USERNAME', '[Não configurado]')}")
    print("=" * 60)
    
    # Tentar inicializar banco
    try:
        initialize_database()
    except Exception as e:
        print(f"⚠️ Aviso na inicialização: {e}")
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)