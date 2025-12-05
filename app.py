from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import uuid
import re
from sqlalchemy import text  # <-- IMPORTANTE: Adicionar esta linha!
from urllib.parse import urlparse

# ========================================
# CONFIGURAÇÕES
# ========================================

app = Flask(__name__)

def get_database_url():
    """Obtém e corrige a URL do banco de dados para o Render"""
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url:
        print(f"🔗 Database URL recebida: {database_url}")
        
        # Verificar se é uma URL completa
        if not database_url.startswith('postgres://') and not database_url.startswith('postgresql://'):
            print("❌ URL do banco parece incompleta ou malformada")
            # Tentar construir a URL completa
            if 'postgres' in database_url:
                # Extrair partes da string
                try:
                    # Exemplo: "postgresql://user:pass@host:port/dbname"
                    if '@' in database_url:
                        parts = database_url.split('@')
                        creds = parts[0].replace('postgresql://', '')
                        host_db = parts[1]
                        
                        user_pass = creds.split(':')
                        username = user_pass[0]
                        password = user_pass[1] if len(user_pass) > 1 else ''
                        
                        # Reconstruir URL
                        database_url = f"postgresql://{username}:{password}@{host_db}"
                        print(f"🔄 URL reconstruída: {database_url.split('@')[0]}@...")
                except Exception as e:
                    print(f"⚠️ Não foi possível reconstruir URL: {e}")
        
        # Convertendo postgres:// para postgresql://
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
            print("🔄 URL convertida para postgresql://")
    
    # Se não tiver URL, usar SQLite
    if not database_url:
        database_url = 'sqlite:///netfyber.db'
        print("📁 Usando SQLite (desenvolvimento)")
    
    print(f"🏁 URL final do banco: {database_url[:50]}...")
    return database_url

# Configurações
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
DATABASE_URL = get_database_url()
ADMIN_URL_PREFIX = os.environ.get('ADMIN_URL_PREFIX', '/gestao-exclusiva-netfyber')
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'netfyber_admin')
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@netfyber.com')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Admin@Netfyber2025!')

app.config['SECRET_KEY'] = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)
app.config['UPLOAD_FOLDER'] = 'static/uploads/blog'
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# ========================================
# CONFIGURAÇÃO PARA RENDER.COM
# ========================================

if 'RENDER' in os.environ:
    print("🚀 Ambiente Render detectado - Ajustando configurações...")
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_recycle': 300,
        'pool_pre_ping': True,
        'pool_size': 5,
        'max_overflow': 10,
    }

# ========================================
# INICIALIZAÇÃO DO BANCO
# ========================================

db = SQLAlchemy(app)

# ========================================
# MODELOS DO BANCO DE DADOS
# ========================================

class AdminUser(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(512), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Plano(db.Model):
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
    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(100), unique=True, nullable=False)
    valor = db.Column(db.Text, nullable=False)
    descricao = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    conteudo = db.Column(db.Text, nullable=False)
    resumo = db.Column(db.Text, nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    imagem = db.Column(db.String(200), default='default.jpg')
    link_materia = db.Column(db.String(500), nullable=False)
    data_publicacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_data_formatada(self):
        try:
            return self.data_publicacao.strftime('%d/%m/%Y')
        except:
            return "Data não disponível"

    def get_imagem_url(self):
        if self.imagem and self.imagem != 'default.jpg':
            return f"/static/uploads/blog/{secure_filename(self.imagem)}"
        return "/static/images/blog/default.jpg"

# ========================================
# LOGIN MANAGER
# ========================================

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'
login_manager.login_message = "Por favor, faça login para acessar esta página."
login_manager.login_message_category = "warning"

@login_manager.user_loader
def load_user(user_id):
    return AdminUser.query.get(int(user_id))

# ========================================
# FUNÇÕES AUXILIARES - CRÍTICO: CORRIGIDO!
# ========================================

def get_configs():
    """Busca configurações do banco - Segura para erros"""
    try:
        # CORREÇÃO: Usar text() para SQL bruto no SQLAlchemy 2.0+
        db.session.execute(text('SELECT 1'))  # <-- AQUI ESTÁ A CORREÇÃO!
        
        configs = {}
        for config in Configuracao.query.all():
            configs[config.chave] = config.valor
        
        print(f"✅ Configurações carregadas: {len(configs)} itens")
        return configs
        
    except Exception as e:
        print(f"⚠️ Erro ao buscar configurações (usando padrão): {e}")
        # Retorna configurações padrão
        return {
            'telefone_contato': '(63) 8494-1778',
            'email_contato': 'contato@netfyber.com',
            'endereco': 'AV. Tocantins – 934, Centro – Sítio Novo – TO',
            'horario_segunda_sexta': '08h às 18h',
            'horario_sabado': '08h às 13h',
            'whatsapp_numero': '556384941778',
            'instagram_url': 'https://www.instagram.com/netfybertelecom',
            'hero_imagem': 'images/familia.png',
            'hero_titulo': 'Internet de Alta Velocidade',
            'hero_subtitulo': 'Conecte sua família ao futuro com a NetFyber Telecom'
        }

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file):
    if not file or file.filename == '':
        return None
    
    if not allowed_file(file.filename):
        return None
    
    try:
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        return unique_filename
    except Exception as e:
        print(f"❌ Erro ao salvar arquivo: {e}")
        return None

# ========================================
# CONTEXT PROCESSOR - CRÍTICO!
# ========================================

@app.context_processor
def inject_configs():
    """INJEÇÃO GLOBAL - Faz configs estar disponível em TODOS os templates"""
    return {'configs': get_configs()}

# ========================================
# ROTAS PÚBLICAS
# ========================================

@app.route('/')
def index():
    return render_template('public/index.html')

@app.route('/planos')
def planos():
    try:
        planos_data = Plano.query.filter_by(ativo=True).order_by(Plano.ordem_exibicao).all()
        return render_template('public/planos.html', planos=planos_data)
    except Exception as e:
        print(f"❌ Erro /planos: {e}")
        return render_template('public/planos.html', planos=[])

@app.route('/blog')
def blog():
    try:
        posts = Post.query.filter_by(ativo=True).order_by(Post.data_publicacao.desc()).all()
        return render_template('public/blog.html', posts=posts)
    except Exception as e:
        print(f"❌ Erro /blog: {e}")
        return render_template('public/blog.html', posts=[])

@app.route('/velocimetro')
def velocimetro():
    return render_template('public/velocimetro.html')

@app.route('/sobre')
def sobre():
    return render_template('public/sobre.html')

# ========================================
# ROTA FAVICON
# ========================================

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    )

# ========================================
# ROTAS ADMINISTRATIVAS - LOGIN CORRIGIDO!
# ========================================

@app.route(f'{ADMIN_URL_PREFIX}/login', methods=['GET', 'POST'])
def admin_login():
    """Login administrativo - CORRIGIDO"""
    if current_user.is_authenticated:
        return redirect(url_for('admin_planos'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Preencha todos os campos', 'error')
            return render_template('auth/login.html')
        
        try:
            # Tentar autenticar com as credenciais do ambiente primeiro
            if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                # Verificar se o usuário existe no banco
                user = AdminUser.query.filter_by(username=username).first()
                if not user:
                    # Criar usuário se não existir
                    user = AdminUser(
                        username=username,
                        email=ADMIN_EMAIL,
                        is_active=True
                    )
                    user.set_password(password)
                    db.session.add(user)
                    db.session.commit()
                    print(f"👤 Usuário admin criado: {username}")
                
                # Fazer login
                if user.check_password(password):
                    login_user(user)
                    flash('Login realizado com sucesso!', 'success')
                    print(f"✅ Login bem-sucedido para: {username}")
                    return redirect(url_for('admin_planos'))
                else:
                    flash('Credenciais inválidas', 'error')
            else:
                # Tentar usuário do banco
                user = AdminUser.query.filter_by(username=username).first()
                if user and user.check_password(password):
                    login_user(user)
                    flash('Login realizado!', 'success')
                    return redirect(url_for('admin_planos'))
                else:
                    flash('Credenciais inválidas', 'error')
        except Exception as e:
            print(f"❌ Erro no login: {e}")
            flash(f'Erro no servidor: {str(e)}', 'error')
    
    return render_template('auth/login.html')

@app.route(f'{ADMIN_URL_PREFIX}/logout')
@login_required
def admin_logout():
    logout_user()
    flash('Logout realizado', 'info')
    return redirect(url_for('admin_login'))

@app.route(f'{ADMIN_URL_PREFIX}/planos')
@login_required
def admin_planos():
    try:
        planos = Plano.query.order_by(Plano.ordem_exibicao).all()
        return render_template('admin/planos.html', planos=planos)
    except Exception as e:
        print(f"❌ Erro admin_planos: {e}")
        flash('Erro ao carregar planos', 'error')
        return render_template('admin/planos.html', planos=[])

@app.route(f'{ADMIN_URL_PREFIX}/blog')
@login_required
def admin_blog():
    try:
        posts = Post.query.order_by(Post.data_publicacao.desc()).all()
        return render_template('admin/blog.html', posts=posts)
    except Exception as e:
        print(f"❌ Erro admin_blog: {e}")
        flash('Erro ao carregar posts', 'error')
        return render_template('admin/blog.html', posts=[])

@app.route(f'{ADMIN_URL_PREFIX}/configuracoes', methods=['GET', 'POST'])
@login_required
def admin_configuracoes():
    if request.method == 'POST':
        try:
            for chave, valor in request.form.items():
                if chave not in ['csrf_token'] and valor.strip():
                    config = Configuracao.query.filter_by(chave=chave).first()
                    if config:
                        config.valor = valor.strip()
                    else:
                        config = Configuracao(chave=chave, valor=valor.strip())
                        db.session.add(config)
            
            db.session.commit()
            flash('Configurações salvas!', 'success')
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro salvar configurações: {e}")
            flash(f'Erro: {str(e)}', 'error')
    
    return render_template('admin/configuracoes.html')

# ========================================
# INICIALIZAÇÃO DO BANCO
# ========================================

def init_database():
    """Inicializa o banco de dados com dados padrão"""
    with app.app_context():
        try:
            print("🔧 Inicializando banco de dados...")
            
            # Criar tabelas se não existirem
            db.create_all()
            print("✅ Tabelas criadas")
            
            # Criar usuário admin a partir das variáveis de ambiente
            admin_username = os.environ.get('ADMIN_USERNAME', 'netfyber_admin')
            admin_password = os.environ.get('ADMIN_PASSWORD', 'Admin@Netfyber2025!')
            admin_email = os.environ.get('ADMIN_EMAIL', 'admin@netfyber.com')
            
            admin = AdminUser.query.filter_by(username=admin_username).first()
            if not admin:
                print(f"👤 Criando usuário admin: {admin_username}")
                admin = AdminUser(
                    username=admin_username,
                    email=admin_email,
                    is_active=True
                )
                admin.set_password(admin_password)
                db.session.add(admin)
                db.session.commit()
                print(f"✅ Admin criado: {admin_username}/{admin_password}")
            
            # Configurações padrão
            configs_padrao = {
                'telefone_contato': '(63) 8494-1778',
                'email_contato': 'contato@netfyber.com',
                'endereco': 'AV. Tocantins – 934, Centro – Sítio Novo – TO',
                'horario_segunda_sexta': '08h às 18h',
                'horario_sabado': '08h às 13h',
                'whatsapp_numero': '556384941778',
                'instagram_url': 'https://www.instagram.com/netfybertelecom',
                'hero_imagem': 'images/familia.png',
                'hero_titulo': 'Internet de Alta Velocidade',
                'hero_subtitulo': 'Conecte sua família ao futuro com a NetFyber Telecom'
            }
            
            for chave, valor in configs_padrao.items():
                config = Configuracao.query.filter_by(chave=chave).first()
                if not config:
                    config = Configuracao(chave=chave, valor=valor)
                    db.session.add(config)
                    print(f"⚙️  Configuração padrão: {chave}")
            
            db.session.commit()
            print("🎉 Banco inicializado com sucesso!")
            
        except Exception as e:
            print(f"❌ Erro inicialização banco: {e}")
            db.session.rollback()

# ========================================
# HEALTH CHECK
# ========================================

@app.route('/health')
def health_check():
    try:
        db.session.execute(text('SELECT 1'))
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'database': 'disconnected',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

# ========================================
# HANDLERS DE ERRO
# ========================================

@app.errorhandler(404)
def not_found_error(error):
    return render_template('public/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('public/500.html'), 500

@app.errorhandler(403)
def forbidden_error(error):
    return render_template('public/403.html'), 403

# ========================================
# INICIALIZAÇÃO
# ========================================

# Inicializar banco de dados
init_database()

# ========================================
# MAIN
# ========================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    print(f"🚀 Iniciando NetFyber na porta {port}...")
    print(f"🔗 URL do Admin: {ADMIN_URL_PREFIX}/login")
    print(f"👤 Usuário: {ADMIN_USERNAME}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug,
        threaded=True
    )