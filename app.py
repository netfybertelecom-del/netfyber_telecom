"""
app.py - Aplicação NetFyber Telecom
Versão corrigida para Flask 2.3+ (sem before_first_request)
"""

import os
import uuid
import bleach
import secrets
import re
from urllib.parse import urlparse
from datetime import datetime, timedelta

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# ========================================
# CONFIGURAÇÃO DA APLICAÇÃO
# ========================================

app = Flask(__name__)

# CONFIGURAÇÕES CRÍTICAS PARA RENDER
# ========================================

# 1. SECRET_KEY - Essencial para sessões seguras
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# 2. DATABASE_URL - CORREÇÃO CRÍTICA PARA SSL NO RENDER
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///netfyber.db')

# CORREÇÃO PARA RENDER: Converter postgres:// para postgresql:// e adicionar SSL
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# FORÇAR SSL NO RENDER (OBRIGATÓRIO)
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    if '?' in DATABASE_URL:
        DATABASE_URL += '&sslmode=require'
    else:
        DATABASE_URL += '?sslmode=require'

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 3. CONFIGURAÇÕES DE POOL DE CONEXÕES
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 300,
    'pool_pre_ping': True,
    'pool_size': 5,
    'max_overflow': 10,
    'pool_timeout': 30,
}

# 4. CONFIGURAÇÕES DE SEGURANÇA
ADMIN_URL_PREFIX = os.environ.get('ADMIN_URL_PREFIX', '/gestao-exclusiva-netfyber')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)

# 5. CONFIGURAÇÕES DE UPLOAD
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads', 'blog')
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8MB
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# ========================================
# INICIALIZAÇÃO DAS EXTENSÕES
# ========================================

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'
login_manager.login_message = "Por favor, faça login para acessar esta área."

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

class Configuracao(db.Model):
    __tablename__ = 'configuracoes'
    
    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(100), unique=True, nullable=False)
    valor = db.Column(db.Text, nullable=False)
    descricao = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
        
        # Processar formatação simples
        content = self.conteudo
        content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
        content = re.sub(r'\*(.*?)\*', r'<em>\1</em>', content)
        content = content.replace('\n', '<br>')
        
        # Sanitizar
        allowed_tags = ['p', 'br', 'strong', 'em', 'b', 'i', 'u', 'a', 
                       'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'blockquote']
        allowed_attrs = {'a': ['href', 'target', 'rel', 'title']}
        
        sanitized = bleach.clean(
            content,
            tags=allowed_tags,
            attributes=allowed_attrs,
            strip=True
        )
        
        # Adicionar target=_blank para links externos
        def add_link_attributes(attrs, new):
            href = attrs.get((None, 'href'), '')
            if href and href.startswith(('http://', 'https://')):
                attrs[(None, 'target')] = '_blank'
                attrs[(None, 'rel')] = 'noopener noreferrer'
            return attrs
        
        sanitized = bleach.linkify(sanitized, callbacks=[add_link_attributes])
        return sanitized
    
    def get_data_formatada(self):
        return self.data_publicacao.strftime('%d/%m/%Y')
    
    def get_imagem_url(self):
        if not self.imagem or self.imagem == 'default.jpg':
            return '/static/images/blog/default.jpg'
        return f'/static/uploads/blog/{self.imagem}'

# ========================================
# INICIALIZAÇÃO DO BANCO (FIX para Flask 2.3+)
# ========================================

_db_initialized = False

def init_database():
    """Inicializa banco de dados - Nova forma para Flask 2.3+"""
    global _db_initialized
    
    if _db_initialized:
        return
    
    try:
        with app.app_context():
            print("[INIT] Criando tabelas...")
            db.create_all()
            
            # Criar usuário admin se não existir
            if not AdminUser.query.filter_by(username='admin').first():
                print("[INIT] Criando usuário admin...")
                admin = AdminUser(
                    username='admin',
                    email='admin@netfyber.com',
                    is_active=True
                )
                admin.set_password('Admin@123')
                db.session.add(admin)
            
            # Criar configurações padrão
            if Configuracao.query.count() == 0:
                print("[INIT] Criando configurações padrão...")
                configs = [
                    ('telefone_contato', '(63) 8494-1778'),
                    ('email_contato', 'contato@netfyber.com'),
                    ('endereco', 'AV. Tocantins – 934, Centro – Sítio Novo – TO'),
                    ('horario_segunda_sexta', '08h às 18h'),
                    ('horario_sabado', '08h às 13h'),
                    ('whatsapp_numero', '556384941778'),
                    ('instagram_url', 'https://www.instagram.com/netfybertelecom'),
                    ('hero_imagem', 'images/familia.png'),
                    ('hero_titulo', 'Internet de Alta Velocidade'),
                    ('hero_subtitulo', 'Conecte sua família ao futuro com a NetFyber Telecom'),
                ]
                
                for chave, valor in configs:
                    config = Configuracao(chave=chave, valor=valor)
                    db.session.add(config)
            
            # Criar planos padrão
            if Plano.query.count() == 0:
                print("[INIT] Criando planos padrão...")
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
            
            db.session.commit()
            print("[INIT] Banco inicializado com sucesso!")
            _db_initialized = True
            
    except Exception as e:
        print(f"[ERRO] Falha ao inicializar banco: {e}")

# ========================================
# MIDDLEWARE - Executa antes de cada request
# ========================================

@app.before_request
def before_request_handler():
    """Executa antes de cada request"""
    if not _db_initialized:
        init_database()

# ========================================
# FUNÇÕES AUXILIARES
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
    except:
        return {}

def sanitize_input(text):
    if not text:
        return ""
    return bleach.clean(text.strip(), tags=[], attributes={}, strip=True)

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
    except:
        planos_data = []
    return render_template('public/planos.html', planos=planos_data, configs=get_configs())

@app.route('/blog')
def blog():
    try:
        posts = Post.query.filter_by(ativo=True).order_by(Post.data_publicacao.desc()).all()
    except:
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
                user.last_login = datetime.utcnow()
                db.session.commit()
                flash('Login realizado com sucesso!', 'success')
                return redirect(url_for('admin_planos'))
            else:
                flash('Credenciais inválidas.', 'error')
        except Exception as e:
            flash(f'Erro: {str(e)}', 'error')
    
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
    except:
        planos_data = []
        flash('Erro ao carregar planos.', 'error')
    return render_template('admin/planos.html', planos=planos_data)

@app.route(f'{ADMIN_URL_PREFIX}/planos/adicionar', methods=['GET', 'POST'])
@login_required
def adicionar_plano():
    if request.method == 'POST':
        try:
            novo_plano = Plano(
                nome=sanitize_input(request.form['nome']),
                preco=sanitize_input(request.form['preco']),
                features=sanitize_input(request.form['features']),
                velocidade=sanitize_input(request.form.get('velocidade', '')),
                recomendado='recomendado' in request.form
            )
            db.session.add(novo_plano)
            db.session.commit()
            flash('Plano adicionado com sucesso!', 'success')
            return redirect(url_for('admin_planos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {str(e)}', 'error')
    return render_template('admin/plano_form.html')

@app.route(f'{ADMIN_URL_PREFIX}/planos/<int:plano_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_plano(plano_id):
    try:
        plano = Plano.query.get_or_404(plano_id)
    except:
        flash('Plano não encontrado.', 'error')
        return redirect(url_for('admin_planos'))
    
    if request.method == 'POST':
        try:
            plano.nome = sanitize_input(request.form['nome'])
            plano.preco = sanitize_input(request.form['preco'])
            plano.features = sanitize_input(request.form['features'])
            plano.velocidade = sanitize_input(request.form.get('velocidade', ''))
            plano.recomendado = 'recomendado' in request.form
            db.session.commit()
            flash('Plano atualizado!', 'success')
            return redirect(url_for('admin_planos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {str(e)}', 'error')
    
    return render_template('admin/plano_form.html', plano=plano)

@app.route(f'{ADMIN_URL_PREFIX}/planos/<int:plano_id>/excluir', methods=['POST'])
@login_required
def excluir_plano(plano_id):
    try:
        plano = Plano.query.get_or_404(plano_id)
        plano.ativo = False
        db.session.commit()
        flash('Plano excluído!', 'success')
    except:
        db.session.rollback()
        flash('Erro ao excluir.', 'error')
    return redirect(url_for('admin_planos'))

@app.route(f'{ADMIN_URL_PREFIX}/blog')
@login_required
def admin_blog():
    try:
        posts = Post.query.filter_by(ativo=True).order_by(Post.data_publicacao.desc()).all()
    except:
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
    
    configs = get_configs()
    return render_template('admin/configuracoes.html', configs=configs)

# ========================================
# UTILITÁRIOS
# ========================================

@app.route('/health')
def health_check():
    return jsonify({'status': 'ok', 'timestamp': datetime.utcnow().isoformat()})

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
# PONTO DE ENTRADA
# ========================================

if __name__ == '__main__':
    # Configurações para desenvolvimento
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get('FLASK_ENV') != 'production'
    
    # Criar diretórios necessários
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs('static/images/blog', exist_ok=True)
    
    # Inicializar banco
    init_database()
    
    # Iniciar servidor
    print(f"🚀 NetFyber iniciando na porta {port}")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)