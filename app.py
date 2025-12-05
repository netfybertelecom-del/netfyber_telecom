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
from sqlalchemy import text
from urllib.parse import urlparse

# ========================================
# CONFIGURAÇÕES
# ========================================

app = Flask(__name__)

def get_database_url():
    """Obtém e corrige a URL do banco de dados"""
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url:
        print(f"🔗 Database URL recebida: {database_url[:50]}...")
        
        # Convertendo postgres:// para postgresql:// (necessário para SQLAlchemy)
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
            print("🔄 URL convertida para postgresql://")
    
    # Se não tiver URL, usar SQLite para desenvolvimento
    if not database_url:
        database_url = 'sqlite:///netfyber.db'
        print("📁 Usando SQLite (desenvolvimento)")
    
    return database_url

# Configurações do app
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
DATABASE_URL = get_database_url()
ADMIN_URL_PREFIX = os.environ.get('ADMIN_URL_PREFIX', '/gestao-exclusiva-netfyber')
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'netfyber_admin')
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@netfyber.com')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Admin@Netfyber2025!')

# Configurações Flask
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)
app.config['UPLOAD_FOLDER'] = 'static/uploads/blog'
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8MB max upload

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# ========================================
# CONFIGURAÇÃO PARA RENDER.COM
# ========================================

if 'RENDER' in os.environ:
    print("🚀 Ambiente Render detectado - Configurando pool de conexões...")
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
# FUNÇÕES AUXILIARES
# ========================================

def get_configs():
    """Busca configurações do banco de dados"""
    try:
        # Testar conexão com o banco
        db.session.execute(text('SELECT 1'))
        
        configs = {}
        for config in Configuracao.query.all():
            configs[config.chave] = config.valor
        
        print(f"✅ Configurações carregadas: {len(configs)} itens")
        return configs
        
    except Exception as e:
        print(f"⚠️ Erro ao buscar configurações: {e}")
        # Configurações padrão
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
    """Verifica se o arquivo é permitido"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file):
    """Salva um arquivo enviado"""
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
        print(f"📁 Arquivo salvo: {unique_filename}")
        return unique_filename
    except Exception as e:
        print(f"❌ Erro ao salvar arquivo: {e}")
        return None

# ========================================
# CONTEXT PROCESSOR
# ========================================

@app.context_processor
def inject_configs():
    """Injeta configurações em todos os templates"""
    return {'configs': get_configs()}

# ========================================
# ROTAS PÚBLICAS
# ========================================

@app.route('/')
def index():
    """Página inicial"""
    return render_template('public/index.html')

@app.route('/planos')
def planos():
    """Página de planos"""
    try:
        planos_data = Plano.query.filter_by(ativo=True).order_by(Plano.ordem_exibicao).all()
        return render_template('public/planos.html', planos=planos_data)
    except Exception as e:
        print(f"❌ Erro ao carregar planos: {e}")
        flash('Erro ao carregar os planos', 'error')
        return render_template('public/planos.html', planos=[])

@app.route('/blog')
def blog():
    """Página do blog"""
    try:
        posts = Post.query.filter_by(ativo=True).order_by(Post.data_publicacao.desc()).all()
        return render_template('public/blog.html', posts=posts)
    except Exception as e:
        print(f"❌ Erro ao carregar blog: {e}")
        flash('Erro ao carregar o blog', 'error')
        return render_template('public/blog.html', posts=[])

@app.route('/velocimetro')
def velocimetro():
    """Página do velocímetro"""
    return render_template('public/velocimetro.html')

@app.route('/sobre')
def sobre():
    """Página sobre nós"""
    return render_template('public/sobre.html')

# ========================================
# ROTAS DE ADMINISTRAÇÃO
# ========================================

@app.route(f'{ADMIN_URL_PREFIX}/login', methods=['GET', 'POST'])
def admin_login():
    """Página de login administrativo"""
    if current_user.is_authenticated:
        return redirect(url_for('admin_planos'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Preencha todos os campos', 'error')
            return render_template('auth/login.html')
        
        try:
            # Verificar se é o usuário admin das variáveis de ambiente
            if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
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
                    print(f"✅ Login bem-sucedido: {username}")
                    return redirect(url_for('admin_planos'))
                else:
                    flash('Credenciais inválidas', 'error')
            else:
                # Tentar autenticar com usuário do banco
                user = AdminUser.query.filter_by(username=username).first()
                if user and user.check_password(password):
                    login_user(user)
                    flash('Login realizado com sucesso!', 'success')
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
    """Logout do administrador"""
    logout_user()
    flash('Logout realizado com sucesso', 'info')
    return redirect(url_for('admin_login'))

@app.route(f'{ADMIN_URL_PREFIX}/planos')
@login_required
def admin_planos():
    """Gerenciamento de planos"""
    try:
        planos = Plano.query.order_by(Plano.ordem_exibicao).all()
        return render_template('admin/planos.html', planos=planos)
    except Exception as e:
        print(f"❌ Erro ao carregar planos admin: {e}")
        flash('Erro ao carregar os planos', 'error')
        return render_template('admin/planos.html', planos=[])

@app.route(f'{ADMIN_URL_PREFIX}/planos/novo', methods=['GET', 'POST'])
@login_required
def admin_novo_plano():
    """Criar novo plano"""
    if request.method == 'POST':
        try:
            nome = request.form.get('nome', '').strip()
            preco = request.form.get('preco', '').strip()
            velocidade = request.form.get('velocidade', '').strip()
            features = request.form.get('features', '').strip()
            recomendado = 'recomendado' in request.form
            ordem_exibicao = int(request.form.get('ordem_exibicao', 0))
            
            if not nome or not preco or not features:
                flash('Preencha todos os campos obrigatórios', 'error')
                return redirect(url_for('admin_novo_plano'))
            
            plano = Plano(
                nome=nome,
                preco=preco,
                velocidade=velocidade,
                features=features,
                recomendado=recomendado,
                ordem_exibicao=ordem_exibicao,
                ativo=True
            )
            
            db.session.add(plano)
            db.session.commit()
            flash('Plano criado com sucesso!', 'success')
            return redirect(url_for('admin_planos'))
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao criar plano: {e}")
            flash(f'Erro ao criar plano: {str(e)}', 'error')
    
    return render_template('admin/plano_form.html', plano=None)

@app.route(f'{ADMIN_URL_PREFIX}/planos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_editar_plano(id):
    """Editar plano existente"""
    plano = Plano.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            plano.nome = request.form.get('nome', '').strip()
            plano.preco = request.form.get('preco', '').strip()
            plano.velocidade = request.form.get('velocidade', '').strip()
            plano.features = request.form.get('features', '').strip()
            plano.recomendado = 'recomendado' in request.form
            plano.ordem_exibicao = int(request.form.get('ordem_exibicao', 0))
            plano.ativo = 'ativo' in request.form
            
            db.session.commit()
            flash('Plano atualizado com sucesso!', 'success')
            return redirect(url_for('admin_planos'))
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao atualizar plano: {e}")
            flash(f'Erro ao atualizar plano: {str(e)}', 'error')
    
    return render_template('admin/plano_form.html', plano=plano)

@app.route(f'{ADMIN_URL_PREFIX}/planos/excluir/<int:id>', methods=['POST'])
@login_required
def admin_excluir_plano(id):
    """Excluir plano"""
    try:
        plano = Plano.query.get_or_404(id)
        db.session.delete(plano)
        db.session.commit()
        flash('Plano excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao excluir plano: {e}")
        flash(f'Erro ao excluir plano: {str(e)}', 'error')
    
    return redirect(url_for('admin_planos'))

@app.route(f'{ADMIN_URL_PREFIX}/blog')
@login_required
def admin_blog():
    """Gerenciamento do blog"""
    try:
        posts = Post.query.order_by(Post.data_publicacao.desc()).all()
        return render_template('admin/blog.html', posts=posts)
    except Exception as e:
        print(f"❌ Erro ao carregar posts admin: {e}")
        flash('Erro ao carregar os posts', 'error')
        return render_template('admin/blog.html', posts=[])

@app.route(f'{ADMIN_URL_PREFIX}/blog/novo', methods=['GET', 'POST'])
@login_required
def admin_novo_post():
    """Criar novo post"""
    if request.method == 'POST':
        try:
            titulo = request.form.get('titulo', '').strip()
            conteudo = request.form.get('conteudo', '').strip()
            resumo = request.form.get('resumo', '').strip()
            categoria = request.form.get('categoria', '').strip()
            link_materia = request.form.get('link_materia', '').strip()
            data_publicacao_str = request.form.get('data_publicacao', '')
            imagem = request.files.get('imagem')
            
            if not titulo or not conteudo or not resumo or not categoria or not link_materia:
                flash('Preencha todos os campos obrigatórios', 'error')
                return redirect(url_for('admin_novo_post'))
            
            # Processar data
            if data_publicacao_str:
                try:
                    data_publicacao = datetime.strptime(data_publicacao_str, '%Y-%m-%d')
                except ValueError:
                    data_publicacao = datetime.utcnow()
            else:
                data_publicacao = datetime.utcnow()
            
            # Processar imagem
            imagem_filename = 'default.jpg'
            if imagem and imagem.filename:
                imagem_filename = save_uploaded_file(imagem)
                if not imagem_filename:
                    imagem_filename = 'default.jpg'
            
            post = Post(
                titulo=titulo,
                conteudo=conteudo,
                resumo=resumo,
                categoria=categoria,
                imagem=imagem_filename,
                link_materia=link_materia,
                data_publicacao=data_publicacao,
                ativo=True
            )
            
            db.session.add(post)
            db.session.commit()
            flash('Post criado com sucesso!', 'success')
            return redirect(url_for('admin_blog'))
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao criar post: {e}")
            flash(f'Erro ao criar post: {str(e)}', 'error')
    
    return render_template('admin/post_form.html', post=None)

@app.route(f'{ADMIN_URL_PREFIX}/blog/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_editar_post(id):
    """Editar post existente"""
    post = Post.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            post.titulo = request.form.get('titulo', '').strip()
            post.conteudo = request.form.get('conteudo', '').strip()
            post.resumo = request.form.get('resumo', '').strip()
            post.categoria = request.form.get('categoria', '').strip()
            post.link_materia = request.form.get('link_materia', '').strip()
            post.ativo = 'ativo' in request.form
            
            # Processar data
            data_publicacao_str = request.form.get('data_publicacao', '')
            if data_publicacao_str:
                try:
                    post.data_publicacao = datetime.strptime(data_publicacao_str, '%Y-%m-%d')
                except ValueError:
                    pass
            
            # Processar imagem
            imagem = request.files.get('imagem')
            if imagem and imagem.filename:
                imagem_filename = save_uploaded_file(imagem)
                if imagem_filename:
                    post.imagem = imagem_filename
            
            db.session.commit()
            flash('Post atualizado com sucesso!', 'success')
            return redirect(url_for('admin_blog'))
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao atualizar post: {e}")
            flash(f'Erro ao atualizar post: {str(e)}', 'error')
    
    return render_template('admin/post_form.html', post=post)

@app.route(f'{ADMIN_URL_PREFIX}/blog/excluir/<int:id>', methods=['POST'])
@login_required
def admin_excluir_post(id):
    """Excluir post"""
    try:
        post = Post.query.get_or_404(id)
        db.session.delete(post)
        db.session.commit()
        flash('Post excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao excluir post: {e}")
        flash(f'Erro ao excluir post: {str(e)}', 'error')
    
    return redirect(url_for('admin_blog'))

@app.route(f'{ADMIN_URL_PREFIX}/configuracoes', methods=['GET', 'POST'])
@login_required
def admin_configuracoes():
    """Gerenciamento de configurações"""
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
            flash('Configurações salvas com sucesso!', 'success')
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao salvar configurações: {e}")
            flash(f'Erro ao salvar configurações: {str(e)}', 'error')
    
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
                print(f"✅ Admin criado: {admin_username}")
            
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
            print(f"❌ Erro na inicialização do banco: {e}")
            db.session.rollback()

# ========================================
# ROTAS DE UTILIDADE
# ========================================

@app.route('/favicon.ico')
def favicon():
    """Favicon do site"""
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    )

@app.route('/health')
def health_check():
    """Endpoint de verificação de saúde da aplicação"""
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
    """Página 404"""
    return render_template('public/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """Página 500"""
    return render_template('public/500.html'), 500

@app.errorhandler(403)
def forbidden_error(error):
    """Página 403"""
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
    
    print(f"🚀 Iniciando NetFyber Telecom...")
    print(f"🌐 URL: http://localhost:{port}")
    print(f"🔗 Painel Admin: {ADMIN_URL_PREFIX}/login")
    print(f"👤 Usuário admin: {ADMIN_USERNAME}")
    print(f"🔧 Modo debug: {debug}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug,
        threaded=True
    )