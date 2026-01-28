"""
app.py - Aplicação NetFyber Telecom
Versão corrigida para Render com PostgreSQL SSL
"""

import os
import uuid
import bleach
import secrets
import re
from urllib.parse import urlparse
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

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
if DATABASE_URL and DATABASE_URL.startswith("postgresql://") and os.environ.get('FLASK_ENV') == 'production':
    if '?' in DATABASE_URL:
        DATABASE_URL += '&sslmode=require'
    else:
        DATABASE_URL += '?sslmode=require'

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 3. CONFIGURAÇÕES DE POOL DE CONEXÕES (IMPORTANTE PARA RENDER)
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 300,           # Reconectar a cada 5 minutos
    'pool_pre_ping': True,         # Verificar conexão antes de usar
    'pool_size': 5,                # Conexões mantidas abertas
    'max_overflow': 10,            # Conexões extras temporárias
    'pool_timeout': 30,            # Timeout para obter conexão
    'connect_args': {
        'connect_timeout': 10,     # Timeout para conectar
        'keepalives_idle': 30,     # Manter conexão viva
        'keepalives_interval': 10,
        'keepalives_count': 5,
        'application_name': 'netfyber-telecom'
    }
}

# 4. CONFIGURAÇÕES DE SEGURANÇA
ADMIN_URL_PREFIX = os.environ.get('ADMIN_URL_PREFIX', '/gestao-exclusiva-netfyber')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# 5. CONFIGURAÇÕES DE UPLOAD (LOCAL PARA DESENVOLVIMENTO)
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads', 'blog')
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8MB
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# 6. CONFIGURAÇÕES CLOUDFLARE R2 (OPCIONAL PARA PRODUÇÃO)
app.config['R2_ENABLED'] = os.environ.get('R2_ENABLED', 'false').lower() == 'true'
if app.config['R2_ENABLED']:
    app.config['R2_ENDPOINT_URL'] = os.environ.get('R2_ENDPOINT_URL', '')
    app.config['R2_PUBLIC_URL'] = os.environ.get('R2_PUBLIC_URL', '')
    app.config['R2_ACCESS_KEY_ID'] = os.environ.get('R2_ACCESS_KEY_ID', '')
    app.config['R2_SECRET_ACCESS_KEY'] = os.environ.get('R2_SECRET_ACCESS_KEY', '')
    app.config['R2_BUCKET'] = os.environ.get('R2_BUCKET', 'netfyber-files')

# ========================================
# INICIALIZAÇÃO DAS EXTENSÕES
# ========================================

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'
login_manager.login_message = "Por favor, faça login para acessar esta área."
login_manager.login_message_category = "warning"

# ========================================
# MIDDLEWARE DE SEGURANÇA
# ========================================

@app.after_request
def add_security_headers(response):
    """Adiciona headers de segurança HTTP"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    if os.environ.get('FLASK_ENV') == 'production':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    return response

# ========================================
# MODELOS DO BANCO DE DADOS
# ========================================

class AdminUser(UserMixin, db.Model):
    """Modelo para usuários administrativos"""
    __tablename__ = 'admin_users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(512), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_superuser = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    last_ip = db.Column(db.String(45), nullable=True)
    
    def set_password(self, password):
        """Cria hash seguro da senha"""
        if len(password) < 8:
            raise ValueError("A senha deve ter pelo menos 8 caracteres")
        self.password_hash = generate_password_hash(
            password, 
            method='pbkdf2:sha256', 
            salt_length=16
        )
    
    def check_password(self, password):
        """Verifica se a senha está correta"""
        return check_password_hash(self.password_hash, password)
    
    def update_login_info(self, ip_address):
        """Atualiza informações do último login"""
        self.last_login = datetime.utcnow()
        self.last_ip = ip_address
        db.session.commit()

class Plano(db.Model):
    """Modelo para planos de internet"""
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
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def get_features_list(self):
        """Retorna lista de características"""
        if not self.features:
            return []
        return [f.strip() for f in self.features.split('\n') if f.strip()]

class Configuracao(db.Model):
    """Modelo para configurações do site"""
    __tablename__ = 'configuracoes'
    
    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(100), unique=True, nullable=False, index=True)
    valor = db.Column(db.Text, nullable=False)
    descricao = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Post(db.Model):
    """Modelo para posts do blog"""
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
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def get_conteudo_html(self):
        """Retorna conteúdo formatado em HTML seguro"""
        if not self.conteudo:
            return ""
        
        # Sanitização básica
        allowed_tags = ['p', 'br', 'strong', 'em', 'b', 'i', 'u', 'a', 
                       'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'blockquote']
        allowed_attrs = {'a': ['href', 'target', 'rel', 'title']}
        
        # Processar markdown simples
        content = self.conteudo
        content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
        content = re.sub(r'\*(.*?)\*', r'<em>\1</em>', content)
        content = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', content, flags=re.MULTILINE)
        content = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', content, flags=re.MULTILINE)
        content = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', content, flags=re.MULTILINE)
        
        # Adicionar quebras de linha
        content = content.replace('\n', '<br>')
        
        # Sanitizar HTML
        sanitized = bleach.clean(
            content,
            tags=allowed_tags,
            attributes=allowed_attrs,
            strip=True
        )
        
        # Adicionar target=_blank para links externos
        sanitized = bleach.linkify(sanitized, callbacks=[
            lambda attrs, new: add_link_attributes(attrs, new)
        ])
        
        return sanitized
    
    def get_data_formatada(self):
        """Retorna data formatada"""
        return self.data_publicacao.strftime('%d/%m/%Y')
    
    def get_imagem_url(self):
        """Retorna URL da imagem"""
        if not self.imagem or self.imagem == 'default.jpg':
            return url_for('static', filename='images/blog/default.jpg')
        
        if current_app.config.get('R2_ENABLED'):
            public_url = current_app.config.get('R2_PUBLIC_URL', '').rstrip('/')
            bucket = current_app.config.get('R2_BUCKET', '')
            if public_url and bucket:
                return f"{public_url}/{bucket}/{self.imagem}"
        
        return url_for('static', filename=f'uploads/blog/{self.imagem}')

def add_link_attributes(attrs, new):
    """Callback para adicionar atributos a links"""
    href = attrs.get((None, 'href'), '')
    if href and href.startswith(('http://', 'https://')):
        attrs[(None, 'target')] = '_blank'
        attrs[(None, 'rel')] = 'noopener noreferrer'
    return attrs

# ========================================
# FUNÇÕES AUXILIARES
# ========================================

@login_manager.user_loader
def load_user(user_id):
    """Carrega usuário para o Flask-Login"""
    try:
        return AdminUser.query.get(int(user_id))
    except:
        return None

def get_configs():
    """Carrega todas as configurações do site"""
    try:
        configs_db = Configuracao.query.all()
        config_dict = {}
        for config in configs_db:
            config_dict[config.chave] = config.valor
        return config_dict
    except Exception as e:
        print(f"[ERRO] Não foi possível carregar configurações: {e}")
        return {}

def sanitize_input(text):
    """Sanitiza entrada do usuário"""
    if not text:
        return ""
    
    # Remover tags HTML/JS perigosas
    text = bleach.clean(text.strip(), tags=[], attributes={}, strip=True)
    
    # Limitar comprimento
    if len(text) > 5000:
        text = text[:5000]
    
    return text

def validate_url(url):
    """Valida URL"""
    try:
        result = urlparse(url)
        return all([result.scheme in ('http', 'https'), result.netloc])
    except:
        return False

def allowed_file(filename):
    """Verifica se arquivo tem extensão permitida"""
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in current_app.config['ALLOWED_EXTENSIONS']

def save_image(file):
    """Salva imagem usando método apropriado (local ou R2)"""
    if not file or not allowed_file(file.filename):
        return None
    
    try:
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        
        # Se R2 habilitado, usar Cloudflare R2
        if current_app.config.get('R2_ENABLED'):
            try:
                import boto3
                from botocore.exceptions import ClientError
                
                s3_client = boto3.client(
                    's3',
                    endpoint_url=current_app.config.get('R2_ENDPOINT_URL'),
                    aws_access_key_id=current_app.config.get('R2_ACCESS_KEY_ID'),
                    aws_secret_access_key=current_app.config.get('R2_SECRET_ACCESS_KEY'),
                    region_name='auto'
                )
                
                bucket_name = current_app.config.get('R2_BUCKET')
                content_type = f'image/{ext}' if ext != 'jpg' else 'image/jpeg'
                
                s3_client.upload_fileobj(
                    file,
                    bucket_name,
                    filename,
                    ExtraArgs={'ContentType': content_type}
                )
                
                print(f"[INFO] Imagem enviada para R2: {filename}")
                return filename
                
            except Exception as e:
                print(f"[ERRO] Falha ao enviar para R2: {e}")
                # Fallback para local
        
        # Fallback: salvar localmente
        upload_dir = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_dir, exist_ok=True)
        
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)
        
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            print(f"[INFO] Imagem salva localmente: {filename}")
            return filename
            
    except Exception as e:
        print(f"[ERRO] Falha ao salvar imagem: {e}")
    
    return None

def delete_image(filename):
    """Exclui imagem"""
    if not filename or filename == 'default.jpg':
        return False
    
    try:
        # Tentar excluir do R2
        if current_app.config.get('R2_ENABLED'):
            try:
                import boto3
                
                s3_client = boto3.client(
                    's3',
                    endpoint_url=current_app.config.get('R2_ENDPOINT_URL'),
                    aws_access_key_id=current_app.config.get('R2_ACCESS_KEY_ID'),
                    aws_secret_access_key=current_app.config.get('R2_SECRET_ACCESS_KEY'),
                    region_name='auto'
                )
                
                bucket_name = current_app.config.get('R2_BUCKET')
                s3_client.delete_object(Bucket=bucket_name, Key=filename)
                print(f"[INFO] Imagem excluída do R2: {filename}")
                return True
                
            except Exception as e:
                print(f"[ERRO] Falha ao excluir do R2: {e}")
                # Continuar para tentar excluir localmente
        
        # Excluir localmente
        upload_dir = current_app.config['UPLOAD_FOLDER']
        filepath = os.path.join(upload_dir, filename)
        
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"[INFO] Imagem excluída localmente: {filename}")
            return True
            
    except Exception as e:
        print(f"[ERRO] Falha ao excluir imagem: {e}")
    
    return False

# ========================================
# INICIALIZAÇÃO DO BANCO DE DADOS
# ========================================

def init_database():
    """Inicializa banco de dados com dados padrão"""
    print("[INIT] Inicializando banco de dados...")
    
    try:
        # Criar tabelas se não existirem
        db.create_all()
        print("[INIT] Tabelas criadas/verificadas")
        
        # Verificar se já existe usuário admin
        admin_exists = AdminUser.query.filter_by(username='admin').first()
        
        if not admin_exists:
            print("[INIT] Criando usuário admin padrão...")
            
            # Criar usuário admin a partir de variáveis de ambiente
            admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
            admin_password = os.environ.get('ADMIN_PASSWORD', 'Admin@123')
            admin_email = os.environ.get('ADMIN_EMAIL', 'admin@netfyber.com')
            
            admin = AdminUser(
                username=admin_username,
                email=admin_email,
                is_active=True,
                is_superuser=True
            )
            admin.set_password(admin_password)
            
            db.session.add(admin)
            print(f"[INIT] Usuário admin criado: {admin_username}")
        
        # Verificar configurações padrão
        if Configuracao.query.count() == 0:
            print("[INIT] Criando configurações padrão...")
            
            configs_padrao = [
                ('telefone_contato', '(63) 8494-1778', 'Telefone para contato'),
                ('email_contato', 'contato@netfyber.com', 'E-mail para contato'),
                ('endereco', 'AV. Tocantins – 934, Centro – Sítio Novo – TO', 'Endereço da empresa'),
                ('horario_segunda_sexta', '08h às 18h', 'Horário de atendimento'),
                ('horario_sabado', '08h às 13h', 'Horário de sábado'),
                ('whatsapp_numero', '556384941778', 'Número do WhatsApp'),
                ('instagram_url', 'https://www.instagram.com/netfybertelecom', 'URL do Instagram'),
                ('hero_imagem', 'images/familia.png', 'Imagem do hero'),
                ('hero_titulo', 'Internet de Alta Velocidade', 'Título principal'),
                ('hero_subtitulo', 'Conecte sua família ao futuro com a NetFyber Telecom', 'Subtítulo'),
            ]
            
            for chave, valor, descricao in configs_padrao:
                config = Configuracao(chave=chave, valor=valor, descricao=descricao)
                db.session.add(config)
            
            print("[INIT] Configurações padrão criadas")
        
        # Verificar planos padrão
        if Plano.query.count() == 0:
            print("[INIT] Criando planos padrão...")
            
            planos_padrao = [
                Plano(
                    nome='100 MEGA',
                    preco='89,90',
                    velocidade='100 Mbps',
                    features='Wi-Fi Grátis\nInstalação Grátis\nSuporte 24h\nFibra Óptica',
                    recomendado=False,
                    ordem_exibicao=1,
                    ativo=True
                ),
                Plano(
                    nome='200 MEGA',
                    preco='99,90',
                    velocidade='200 Mbps',
                    features='Wi-Fi Grátis\nInstalação Grátis\nSuporte 24h\nFibra Óptica\nModem Incluso',
                    recomendado=True,
                    ordem_exibicao=2,
                    ativo=True
                ),
                Plano(
                    nome='400 MEGA',
                    preco='119,90',
                    velocidade='400 Mbps',
                    features='Wi-Fi Grátis\nInstalação Grátis\nSuporte 24h\nFibra Óptica\nModem Incluso\nAntivírus',
                    recomendado=False,
                    ordem_exibicao=3,
                    ativo=True
                ),
            ]
            
            for plano in planos_padrao:
                db.session.add(plano)
            
            print("[INIT] Planos padrão criados")
        
        db.session.commit()
        print("[INIT] Banco de dados inicializado com sucesso!")
        
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO CRÍTICO] Falha ao inicializar banco: {e}")
        import traceback
        traceback.print_exc()
        # Não levantar exceção para permitir que o site funcione em modo limitado

# Executar inicialização na primeira requisição
@app.before_first_request
def initialize():
    """Inicializa banco antes da primeira requisição"""
    init_database()

# ========================================
# ROTAS PÚBLICAS
# ========================================

@app.route('/')
def index():
    """Página inicial"""
    configs = get_configs()
    return render_template('public/index.html', configs=configs)

@app.route('/planos')
def planos():
    """Página de planos"""
    try:
        planos_data = Plano.query.filter_by(ativo=True)\
            .order_by(Plano.ordem_exibicao)\
            .all()
    except Exception as e:
        print(f"[ERRO] Falha ao carregar planos: {e}")
        planos_data = []
    
    configs = get_configs()
    return render_template('public/planos.html', planos=planos_data, configs=configs)

@app.route('/blog')
def blog():
    """Página do blog"""
    try:
        posts = Post.query.filter_by(ativo=True)\
            .order_by(Post.data_publicacao.desc())\
            .all()
    except Exception as e:
        print(f"[ERRO] Falha ao carregar posts: {e}")
        posts = []
    
    configs = get_configs()
    return render_template('public/blog.html', configs=configs, posts=posts)

@app.route('/velocimetro')
def velocimetro():
    """Página do velocímetro"""
    configs = get_configs()
    return render_template('public/velocimetro.html', configs=configs)

@app.route('/sobre')
def sobre():
    """Página sobre nós"""
    configs = get_configs()
    return render_template('public/sobre.html', configs=configs)

# ========================================
# AUTENTICAÇÃO ADMIN
# ========================================

@app.route(f'{ADMIN_URL_PREFIX}/login', methods=['GET', 'POST'])
def admin_login():
    """Página de login administrativo"""
    # Se já estiver autenticado, redirecionar
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    
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
                user.update_login_info(request.remote_addr)
                
                flash(f'Bem-vindo, {user.username}!', 'success')
                
                # Registrar login bem-sucedido
                print(f"[AUTH] Login bem-sucedido: {user.username} from {request.remote_addr}")
                
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Credenciais inválidas.', 'error')
                # Registrar tentativa falha
                print(f"[AUTH] Tentativa de login falha: {username} from {request.remote_addr}")
                
        except Exception as e:
            flash(f'Erro no servidor: {str(e)}', 'error')
            print(f"[ERRO] Falha no login: {e}")
    
    return render_template('auth/login.html')

@app.route(f'{ADMIN_URL_PREFIX}/logout')
@login_required
def admin_logout():
    """Logout administrativo"""
    username = current_user.username
    logout_user()
    flash('Você saiu do sistema.', 'info')
    print(f"[AUTH] Logout: {username}")
    return redirect(url_for('admin_login'))

# ========================================
# PAINEL ADMINISTRATIVO
# ========================================

@app.route(f'{ADMIN_URL_PREFIX}/dashboard')
@login_required
def admin_dashboard():
    """Dashboard administrativo"""
    try:
        planos_count = Plano.query.filter_by(ativo=True).count()
        posts_count = Post.query.filter_by(ativo=True).count()
        users_count = AdminUser.query.filter_by(is_active=True).count()
    except Exception as e:
        print(f"[ERRO] Falha ao carregar estatísticas: {e}")
        planos_count = posts_count = users_count = 0
    
    return render_template('admin/dashboard.html',
                         planos_count=planos_count,
                         posts_count=posts_count,
                         users_count=users_count)

@app.route(f'{ADMIN_URL_PREFIX}/planos')
@login_required
def admin_planos():
    """Gerenciar planos"""
    try:
        planos_data = Plano.query.filter_by(ativo=True)\
            .order_by(Plano.ordem_exibicao)\
            .all()
    except Exception as e:
        print(f"[ERRO] Falha ao carregar planos: {e}")
        planos_data = []
        flash('Erro ao carregar planos.', 'error')
    
    return render_template('admin/planos.html', planos=planos_data)

@app.route(f'{ADMIN_URL_PREFIX}/planos/adicionar', methods=['GET', 'POST'])
@login_required
def adicionar_plano():
    """Adicionar novo plano"""
    if request.method == 'POST':
        try:
            nome = sanitize_input(request.form['nome'])
            preco = sanitize_input(request.form['preco'])
            features = sanitize_input(request.form['features'])
            velocidade = sanitize_input(request.form.get('velocidade', ''))
            recomendado = 'recomendado' in request.form
            
            if not nome or not preco or not features:
                flash('Preencha todos os campos obrigatórios.', 'error')
                return redirect(request.url)
            
            novo_plano = Plano(
                nome=nome,
                preco=preco,
                features=features,
                velocidade=velocidade,
                recomendado=recomendado,
                ordem_exibicao=request.form.get('ordem_exibicao', 0)
            )
            
            db.session.add(novo_plano)
            db.session.commit()
            
            flash(f'Plano "{nome}" adicionado com sucesso!', 'success')
            return redirect(url_for('admin_planos'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao adicionar plano: {str(e)}', 'error')
            print(f"[ERRO] Falha ao adicionar plano: {e}")
    
    return render_template('admin/plano_form.html')

@app.route(f'{ADMIN_URL_PREFIX}/planos/<int:plano_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_plano(plano_id):
    """Editar plano existente"""
    try:
        plano = Plano.query.get_or_404(plano_id)
    except Exception as e:
        flash('Plano não encontrado.', 'error')
        return redirect(url_for('admin_planos'))
    
    if request.method == 'POST':
        try:
            plano.nome = sanitize_input(request.form['nome'])
            plano.preco = sanitize_input(request.form['preco'])
            plano.features = sanitize_input(request.form['features'])
            plano.velocidade = sanitize_input(request.form.get('velocidade', ''))
            plano.recomendado = 'recomendado' in request.form
            plano.ordem_exibicao = int(request.form.get('ordem_exibicao', 0))
            plano.updated_at = datetime.utcnow()
            
            db.session.commit()
            flash('Plano atualizado com sucesso!', 'success')
            return redirect(url_for('admin_planos'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar plano: {str(e)}', 'error')
            print(f"[ERRO] Falha ao atualizar plano: {e}")
    
    return render_template('admin/plano_form.html', plano=plano)

@app.route(f'{ADMIN_URL_PREFIX}/planos/<int:plano_id>/excluir', methods=['POST'])
@login_required
def excluir_plano(plano_id):
    """Excluir plano (soft delete)"""
    try:
        plano = Plano.query.get_or_404(plano_id)
        plano_nome = plano.nome
        plano.ativo = False
        plano.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash(f'Plano "{plano_nome}" excluído com sucesso!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Erro ao excluir plano.', 'error')
        print(f"[ERRO] Falha ao excluir plano: {e}")
    
    return redirect(url_for('admin_planos'))

# ========================================
# GERENCIAMENTO DO BLOG
# ========================================

@app.route(f'{ADMIN_URL_PREFIX}/blog')
@login_required
def admin_blog():
    """Gerenciar posts do blog"""
    try:
        posts = Post.query.filter_by(ativo=True)\
            .order_by(Post.data_publicacao.desc())\
            .all()
    except Exception as e:
        print(f"[ERRO] Falha ao carregar posts: {e}")
        posts = []
        flash('Erro ao carregar posts.', 'error')
    
    return render_template('admin/blog.html', posts=posts)

@app.route(f'{ADMIN_URL_PREFIX}/blog/adicionar', methods=['GET', 'POST'])
@login_required
def adicionar_post():
    """Adicionar novo post"""
    if request.method == 'POST':
        try:
            # Validação básica
            titulo = sanitize_input(request.form.get('titulo', ''))
            conteudo = request.form.get('conteudo', '')
            categoria = sanitize_input(request.form.get('categoria', ''))
            link_materia = request.form.get('link_materia', '')
            data_publicacao = request.form.get('data_publicacao', '')
            
            if not all([titulo, conteudo, categoria, link_materia, data_publicacao]):
                flash('Preencha todos os campos obrigatórios.', 'error')
                return redirect(request.url)
            
            # Validar URL
            if not validate_url(link_materia):
                flash('URL da matéria inválida.', 'error')
                return redirect(request.url)
            
            # Validar data
            try:
                data_obj = datetime.strptime(data_publicacao, '%d/%m/%Y')
            except ValueError:
                flash('Formato de data inválido. Use DD/MM/AAAA.', 'error')
                return redirect(request.url)
            
            # Processar imagem
            imagem_filename = 'default.jpg'
            if 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename != '':
                    saved_filename = save_image(file)
                    if saved_filename:
                        imagem_filename = saved_filename
            
            # Criar resumo
            conteudo_texto = re.sub(r'<[^>]+>', '', conteudo)
            resumo = conteudo_texto[:150] + '...' if len(conteudo_texto) > 150 else conteudo_texto
            
            # Criar post
            novo_post = Post(
                titulo=titulo,
                conteudo=conteudo,
                resumo=resumo,
                categoria=categoria,
                imagem=imagem_filename,
                link_materia=link_materia,
                data_publicacao=data_obj
            )
            
            db.session.add(novo_post)
            db.session.commit()
            
            flash(f'Post "{titulo}" adicionado com sucesso!', 'success')
            return redirect(url_for('admin_blog'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao adicionar post: {str(e)}', 'error')
            print(f"[ERRO] Falha ao adicionar post: {e}")
    
    return render_template('admin/post_form.html', post=None, 
                         data_hoje=datetime.now().strftime('%d/%m/%Y'))

@app.route(f'{ADMIN_URL_PREFIX}/blog/<int:post_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_post(post_id):
    """Editar post existente"""
    try:
        post = Post.query.get_or_404(post_id)
    except Exception as e:
        flash('Post não encontrado.', 'error')
        return redirect(url_for('admin_blog'))
    
    if request.method == 'POST':
        try:
            # Atualizar dados básicos
            post.titulo = sanitize_input(request.form.get('titulo', ''))
            post.conteudo = request.form.get('conteudo', '')
            post.categoria = sanitize_input(request.form.get('categoria', ''))
            post.link_materia = request.form.get('link_materia', '')
            post.updated_at = datetime.utcnow()
            
            # Validar URL
            if not validate_url(post.link_materia):
                flash('URL da matéria inválida.', 'error')
                return redirect(request.url)
            
            # Validar data
            try:
                data_publicacao = datetime.strptime(
                    request.form.get('data_publicacao', ''), 
                    '%d/%m/%Y'
                )
                post.data_publicacao = data_publicacao
            except ValueError:
                flash('Formato de data inválido. Use DD/MM/AAAA.', 'error')
                return redirect(request.url)
            
            # Atualizar imagem se fornecida
            if 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename != '':
                    saved_filename = save_image(file)
                    if saved_filename:
                        # Excluir imagem antiga se não for default
                        if post.imagem and post.imagem != 'default.jpg':
                            delete_image(post.imagem)
                        
                        post.imagem = saved_filename
            
            # Atualizar resumo
            conteudo_texto = re.sub(r'<[^>]+>', '', post.conteudo)
            post.resumo = conteudo_texto[:150] + '...' if len(conteudo_texto) > 150 else conteudo_texto
            
            db.session.commit()
            flash('Post atualizado com sucesso!', 'success')
            return redirect(url_for('admin_blog'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar post: {str(e)}', 'error')
            print(f"[ERRO] Falha ao atualizar post: {e}")
    
    return render_template('admin/post_form.html', post=post,
                         data_hoje=post.get_data_formatada())

@app.route(f'{ADMIN_URL_PREFIX}/blog/<int:post_id>/excluir', methods=['POST'])
@login_required
def excluir_post(post_id):
    """Excluir post (soft delete)"""
    try:
        post = Post.query.get_or_404(post_id)
        post_titulo = post.titulo
        
        # Excluir imagem se não for default
        if post.imagem and post.imagem != 'default.jpg':
            delete_image(post.imagem)
        
        post.ativo = False
        post.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash(f'Post "{post_titulo}" excluído com sucesso!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Erro ao excluir post.', 'error')
        print(f"[ERRO] Falha ao excluir post: {e}")
    
    return redirect(url_for('admin_blog'))

# ========================================
# CONFIGURAÇÕES DO SITE
# ========================================

@app.route(f'{ADMIN_URL_PREFIX}/configuracoes', methods=['GET', 'POST'])
@login_required
def admin_configuracoes():
    """Gerenciar configurações do site"""
    if request.method == 'POST':
        try:
            for chave, valor in request.form.items():
                if chave not in ['csrf_token', 'submit'] and valor.strip():
                    config = Configuracao.query.filter_by(chave=chave).first()
                    
                    if config:
                        config.valor = sanitize_input(valor)
                        config.updated_at = datetime.utcnow()
                    else:
                        config = Configuracao(
                            chave=chave,
                            valor=sanitize_input(valor),
                            descricao=f'Configuração {chave}'
                        )
                        db.session.add(config)
            
            db.session.commit()
            flash('Configurações atualizadas com sucesso!', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar configurações: {str(e)}', 'error')
            print(f"[ERRO] Falha ao atualizar configurações: {e}")
    
    configs = get_configs()
    return render_template('admin/configuracoes.html', configs=configs)

# ========================================
# UTILITÁRIOS E HEALTH CHECKS
# ========================================

@app.route('/health')
def health_check():
    """Endpoint de verificação de saúde"""
    try:
        # Verificar conexão com banco
        db.session.execute('SELECT 1')
        db_status = 'healthy'
    except Exception as e:
        db_status = f'unhealthy: {str(e)}'
    
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.utcnow().isoformat(),
        'database': db_status,
        'environment': os.environ.get('FLASK_ENV', 'unknown')
    })

@app.route('/debug/db')
def debug_db():
    """Endpoint de debug do banco (apenas desenvolvimento)"""
    if os.environ.get('FLASK_ENV') != 'development':
        abort(404)
    
    try:
        result = db.session.execute('SELECT version()').fetchone()
        db_version = result[0] if result else 'unknown'
        
        tables = db.engine.table_names()
        
        return jsonify({
            'database_url': current_app.config['SQLALCHEMY_DATABASE_URI'][:50] + '...',
            'db_version': db_version,
            'tables': tables,
            'planos_count': Plano.query.count(),
            'posts_count': Post.query.count(),
            'configs_count': Configuracao.query.count(),
            'users_count': AdminUser.query.count()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========================================
# HANDLERS DE ERRO
# ========================================

@app.errorhandler(404)
def pagina_nao_encontrada(error):
    configs = get_configs()
    return render_template('public/404.html', configs=configs), 404

@app.errorhandler(403)
def acesso_negado(error):
    configs = get_configs()
    return render_template('public/403.html', configs=configs), 403

@app.errorhandler(500)
def erro_servidor(error):
    configs = get_configs()
    return render_template('public/500.html', configs=configs), 500

# ========================================
# PONTO DE ENTRADA
# ========================================

if __name__ == '__main__':
    # Configurações para desenvolvimento
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get('FLASK_ENV') != 'production'
    
    # Garantir que diretórios necessários existam
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs('static/images/blog', exist_ok=True)
    
    # Informações de inicialização
    print("=" * 50)
    print("🚀 NETFYBER TELECOM - INICIANDO")
    print("=" * 50)
    print(f"🔧 Ambiente: {os.environ.get('FLASK_ENV', 'development')}")
    print(f"📊 Banco: {app.config['SQLALCHEMY_DATABASE_URI'][:50]}...")
    print(f"🔐 SSL Forçado: {'Sim' if 'sslmode=require' in app.config['SQLALCHEMY_DATABASE_URI'] else 'Não'}")
    print(f"📁 Upload: {app.config['UPLOAD_FOLDER']}")
    print(f"☁️ Cloudflare R2: {'HABILITADO' if app.config['R2_ENABLED'] else 'DESABILITADO'}")
    print("=" * 50)
    
    # Inicializar banco
    with app.app_context():
        init_database()
    
    # Iniciar servidor
    app.run(host='0.0.0.0', port=port, debug=debug_mode)