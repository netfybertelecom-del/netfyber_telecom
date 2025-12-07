import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import uuid
import bleach
from urllib.parse import urlparse

app = Flask(__name__)

# ========================================
# CONFIGURAÇÕES BÁSICAS
# ========================================

SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:102030@localhost/testenet1')

# IMPORTANTE: Render usa formato postgres://, SQLAlchemy precisa de postgresql://
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

ADMIN_URL_PREFIX = os.environ.get('ADMIN_URL_PREFIX', '/gestao-exclusiva-netfyber')
ADMIN_IPS = os.environ.get('ADMIN_IPS', '127.0.0.1').split(',')
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'netfyber_admin')
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@netfyber.com')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Admin@Netfyber2025!')

app.config['SECRET_KEY'] = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)

# Configuração de upload
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads', 'blog')
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8MB

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

db = SQLAlchemy(app)

# ========================================
# SEGURANÇA SIMPLIFICADA
# ========================================

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'
login_manager.login_message = "Por favor, faça login para acessar esta página."
login_manager.login_message_category = "warning"
login_manager.session_protection = "strong"

# Headers de segurança manuais
@app.after_request
def set_security_headers(response):
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

# ========================================
# VALIDAÇÕES DE SEGURANÇA
# ========================================

def validate_filename(filename):
    """Validação rigorosa de nomes de arquivo"""
    if not filename or filename.strip() != filename:
        return False
    
    filename = secure_filename(filename)
    if '..' in filename or filename.startswith('.') or '/' in filename:
        return False
    
    return True

def sanitize_html(content):
    """Sanitização segura de HTML"""
    if not content:
        return ""
    
    allowed_tags = ['p', 'br', 'strong', 'em', 'b', 'i', 'u', 'a', 'ul', 'ol', 'li']
    allowed_attributes = {
        'a': ['href', 'target', 'rel']
    }
    
    sanitized = bleach.clean(
        content,
        tags=allowed_tags,
        attributes=allowed_attributes,
        strip=True,
        strip_comments=True
    )
    
    sanitized = bleach.linkify(sanitized, callbacks=[
        lambda attrs, new: add_noopener(attrs, new)
    ])
    
    return sanitized

def add_noopener(attrs, new):
    """Adiciona noopener a links externos"""
    href_key = (None, 'href')
    if href_key in attrs:
        href = attrs[href_key]
        if href.startswith(('http://', 'https://')):
            rel_key = (None, 'rel')
            if rel_key in attrs:
                attrs[rel_key] = attrs[rel_key] + ' noopener'
            else:
                attrs[rel_key] = 'noopener'
            attrs[(None, 'target')] = '_blank'
    return attrs

def validate_url(url):
    """Validação segura de URLs"""
    try:
        result = urlparse(url)
        if result.scheme not in ('http', 'https'):
            return False
        if not result.netloc:
            return False
        return True
    except Exception:
        return False

# ========================================
# MODELOS DO BANCO DE DADOS
# ========================================

class AdminUser(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(512), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        """Hash seguro da senha"""
        if len(password) < 8:
            raise ValueError("Senha deve ter pelo menos 8 caracteres")
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verifica senha com proteção"""
        if self.locked_until and datetime.utcnow() < self.locked_until:
            raise ValueError("Conta temporariamente bloqueada")
        
        is_correct = check_password_hash(self.password_hash, password)
        
        if is_correct:
            self.login_attempts = 0
            self.locked_until = None
            self.last_login = datetime.utcnow()
        else:
            self.login_attempts += 1
            if self.login_attempts >= 5:
                self.locked_until = datetime.utcnow() + timedelta(minutes=30)
        
        db.session.commit()
        return is_correct

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
        """Retorna lista de features sanitizada"""
        if not self.features:
            return []
        return [bleach.clean(f.strip()) for f in self.features.split('\n') if f.strip()]

class Configuracao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(100), unique=True, nullable=False)
    valor = db.Column(db.Text, nullable=False)
    descricao = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @staticmethod
    def get_valor(chave, default=None):
        config = Configuracao.query.filter_by(chave=chave).first()
        return bleach.clean(config.valor) if config else default

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

    def get_conteudo_html(self):
        """Retorna o conteúdo sanitizado em HTML seguro"""
        try:
            if not self.conteudo:
                return "<p>Conteúdo não disponível.</p>"
            return sanitize_html(self.conteudo)
        except Exception as e:
            return "<p>Erro ao carregar conteúdo.</p>"

    def get_data_formatada(self):
        try:
            if self.data_publicacao:
                return self.data_publicacao.strftime('%d/%m/%Y')
            return "Data não disponível"
        except Exception:
            return "Data não disponível"

    def get_imagem_url(self):
        if self.imagem and self.imagem != 'default.jpg':
            safe_filename = secure_filename(self.imagem)
            return f"/static/uploads/blog/{safe_filename}"
        return "/static/images/blog/default.jpg"

@login_manager.user_loader
def load_user(user_id):
    return AdminUser.query.get(int(user_id))

# ========================================
# MIDDLEWARE DE SEGURANÇA
# ========================================

@app.before_request
def restrict_admin_access():
    """Restrição de IP para área administrativa"""
    if request.path.startswith(ADMIN_URL_PREFIX):
        client_ip = request.remote_addr
        
        if ADMIN_IPS and client_ip not in ADMIN_IPS:
            print(f"Tentativa de acesso não autorizado de IP: {client_ip} - Path: {request.path}")
            abort(403, description="Acesso não autorizado")

# ========================================
# FUNÇÕES DE UPLOAD SEGURAS
# ========================================

def save_uploaded_file(file):
    """Salvamento seguro de arquivos"""
    if not file or file.filename == '':
        return None
    
    if not validate_filename(file.filename):
        return None
    
    file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    if file_ext not in ALLOWED_EXTENSIONS:
        return None
    
    try:
        filename = f"{uuid.uuid4().hex}.{file_ext}"
        # Garantir que a pasta de upload existe
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            return filename
    except Exception as e:
        print(f"Erro ao salvar arquivo: {e}")
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
    
    return None

def delete_uploaded_file(filename):
    """Exclusão segura de arquivos"""
    if not filename or filename == 'default.jpg':
        return False
    
    try:
        safe_filename = secure_filename(filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
        
        if not os.path.abspath(file_path).startswith(os.path.abspath(app.config['UPLOAD_FOLDER'])):
            return False
            
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
    except Exception as e:
        print(f"Erro ao deletar arquivo {filename}: {e}")
    
    return False

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
        planos_formatados = []
        for plano in planos_data:
            planos_formatados.append({
                'nome': bleach.clean(plano.nome),
                'preco': bleach.clean(plano.preco),
                'features': [bleach.clean(f) for f in plano.get_features_list()],
                'recomendado': plano.recomendado
            })
        return render_template('public/planos.html', planos=planos_formatados, configs=get_configs())
    except Exception as e:
        print(f"Erro na rota /planos: {e}")
        return render_template('public/planos.html', planos=[], configs=get_configs())

@app.route('/blog')
def blog():
    try:
        posts = Post.query.filter_by(ativo=True).order_by(Post.data_publicacao.desc()).all()
        return render_template('public/blog.html', configs=get_configs(), posts=posts)
    except Exception as e:
        print(f"Erro na rota /blog: {e}")
        return render_template('public/blog.html', configs=get_configs(), posts=[])

@app.route('/velocimetro')
def velocimetro():
    return render_template('public/velocimetro.html', configs=get_configs())

@app.route('/sobre')
def sobre():
    return render_template('public/sobre.html', configs=get_configs())

# ========================================
# AUTENTICAÇÃO
# ========================================

@app.route(f'{ADMIN_URL_PREFIX}/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_planos'))
    
    if request.method == 'POST':
        username = bleach.clean(request.form.get('username', '').strip())
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Credenciais inválidas.', 'error')
            return render_template('auth/login.html')
        
        user = AdminUser.query.filter_by(username=username, is_active=True).first()
        
        if user:
            try:
                if user.check_password(password):
                    login_user(user, remember=False)
                    flash('Login realizado com sucesso!', 'success')
                    print(f"Login bem-sucedido para usuário: {username}")
                    
                    next_page = request.args.get('next')
                    if next_page and validate_next_url(next_page):
                        return redirect(next_page)
                    return redirect(url_for('admin_planos'))
                else:
                    flash('Usuário ou senha inválidos.', 'error')
            except ValueError as e:
                flash(str(e), 'error')
        else:
            check_password_hash(generate_password_hash('dummy'), 'dummy_password')
            flash('Usuário ou senha inválidos.', 'error')
    
    return render_template('auth/login.html')

def validate_next_url(next_url):
    """Valida se a URL de redirecionamento é segura"""
    if not next_url:
        return False
    try:
        parsed = urlparse(next_url)
        return not parsed.netloc
    except Exception:
        return False

@app.route(f'{ADMIN_URL_PREFIX}/logout')
@login_required
def admin_logout():
    print(f"Logout do usuário: {current_user.username}")
    logout_user()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('admin_login'))

# ========================================
# ROTAS ADMINISTRATIVAS - BLOG
# ========================================

@app.route(f'{ADMIN_URL_PREFIX}/blog')
@login_required
def admin_blog():
    posts = Post.query.filter_by(ativo=True).order_by(Post.data_publicacao.desc()).all()
    return render_template('admin/blog.html', posts=posts)

@app.route(f'{ADMIN_URL_PREFIX}/blog/adicionar', methods=['GET', 'POST'])
@login_required
def adicionar_post():
    if request.method == 'POST':
        try:
            titulo = bleach.clean(request.form.get('titulo', '').strip())
            conteudo = request.form.get('conteudo', '').strip()
            categoria = bleach.clean(request.form.get('categoria', ''))
            link_materia = request.form.get('link_materia', '').strip()
            data_publicacao_str = request.form.get('data_publicacao', '')
            
            if not all([titulo, conteudo, categoria, link_materia]):
                flash('Todos os campos obrigatórios devem ser preenchidos.', 'error')
                return redirect(request.url)
            
            if not validate_url(link_materia):
                flash('URL da matéria inválida.', 'error')
                return redirect(request.url)
            
            imagem_filename = 'default.jpg'
            if 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename != '':
                    uploaded_filename = save_uploaded_file(file)
                    if uploaded_filename:
                        imagem_filename = uploaded_filename
                    else:
                        flash('Arquivo de imagem inválido.', 'error')
                        return redirect(request.url)
            
            try:
                data_publicacao = datetime.strptime(data_publicacao_str, '%d/%m/%Y')
            except ValueError:
                data_publicacao = datetime.utcnow()
                flash('Data inválida. Usando data atual.', 'warning')
            
            resumo = bleach.clean(conteudo[:150] + '...' if len(conteudo) > 150 else conteudo)
            
            novo_post = Post(
                titulo=titulo,
                conteudo=conteudo,
                resumo=resumo,
                categoria=categoria,
                imagem=imagem_filename,
                link_materia=link_materia,
                data_publicacao=data_publicacao
            )
            
            db.session.add(novo_post)
            db.session.commit()
            
            print(f"Novo post criado por {current_user.username}: {titulo}")
            flash(f'Post "{novo_post.titulo}" adicionado com sucesso!', 'success')
            return redirect(url_for('admin_blog'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao adicionar post: {e}")
            flash('Erro ao adicionar post.', 'error')
    
    data_hoje = datetime.now().strftime('%d/%m/%Y')
    return render_template('admin/post_form.html', post=None, data_hoje=data_hoje)

@app.route(f'{ADMIN_URL_PREFIX}/blog/<int:post_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_post(post_id):
    post = Post.query.get_or_404(post_id)
    
    if request.method == 'POST':
        try:
            if 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename != '':
                    uploaded_filename = save_uploaded_file(file)
                    if uploaded_filename:
                        if post.imagem and post.imagem != 'default.jpg':
                            delete_uploaded_file(post.imagem)
                        post.imagem = uploaded_filename
            
            data_publicacao_str = request.form.get('data_publicacao', '')
            try:
                data_publicacao = datetime.strptime(data_publicacao_str, '%d/%m/%Y')
            except ValueError:
                data_publicacao = post.data_publicacao
                flash('Data inválida. Mantendo data original.', 'warning')
            
            conteudo = request.form.get('conteudo', '').strip()
            resumo = conteudo[:150] + '...' if len(conteudo) > 150 else conteudo
            
            post.titulo = bleach.clean(request.form.get('titulo', '').strip())
            post.conteudo = conteudo
            post.resumo = resumo
            post.categoria = bleach.clean(request.form.get('categoria', ''))
            post.link_materia = request.form.get('link_materia', '').strip()
            post.data_publicacao = data_publicacao
            post.updated_at = datetime.utcnow()
            
            db.session.commit()
            flash('Post atualizado com sucesso!', 'success')
            return redirect(url_for('admin_blog'))
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao atualizar post: {e}")
            flash('Erro ao atualizar post.', 'error')
    
    data_formatada = post.data_publicacao.strftime('%d/%m/%Y')
    return render_template('admin/post_form.html', post=post, data_hoje=data_formatada)

@app.route(f'{ADMIN_URL_PREFIX}/blog/<int:post_id>/excluir', methods=['POST'])
@login_required
def excluir_post(post_id):
    try:
        post = Post.query.get_or_404(post_id)
        if post.imagem and post.imagem != 'default.jpg':
            delete_uploaded_file(post.imagem)
        
        post.ativo = False
        db.session.commit()
        flash(f'Post "{post.titulo}" excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao excluir post: {e}")
        flash('Erro ao excluir post.', 'error')
    
    return redirect(url_for('admin_blog'))

# ========================================
# ROTAS ADMINISTRATIVAS - PLANOS
# ========================================

@app.route(f'{ADMIN_URL_PREFIX}/planos')
@login_required
def admin_planos():
    planos_data = Plano.query.filter_by(ativo=True).order_by(Plano.ordem_exibicao).all()
    return render_template('admin/planos.html', planos=planos_data)

@app.route(f'{ADMIN_URL_PREFIX}/planos/adicionar', methods=['GET', 'POST'])
@login_required
def adicionar_plano():
    if request.method == 'POST':
        try:
            novo_plano = Plano(
                nome=request.form['nome'],
                preco=request.form['preco'],
                features=request.form['features'],
                velocidade=request.form.get('velocidade', ''),
                recomendado='recomendado' in request.form
            )
            db.session.add(novo_plano)
            db.session.commit()
            flash(f'Plano "{novo_plano.nome}" adicionado com sucesso!', 'success')
            return redirect(url_for('admin_planos'))
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao adicionar plano: {e}")
            flash('Erro ao adicionar plano.', 'error')
    
    return render_template('admin/plano_form.html')

@app.route(f'{ADMIN_URL_PREFIX}/planos/<int:plano_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_plano(plano_id):
    plano = Plano.query.get_or_404(plano_id)
    
    if request.method == 'POST':
        try:
            plano.nome = request.form['nome']
            plano.preco = request.form['preco']
            plano.features = request.form['features']
            plano.velocidade = request.form.get('velocidade', '')
            plano.recomendado = 'recomendado' in request.form
            
            db.session.commit()
            flash('Plano atualizado com sucesso!', 'success')
            return redirect(url_for('admin_planos'))
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao atualizar plano: {e}")
            flash('Erro ao atualizar plano.', 'error')
    
    return render_template('admin/plano_form.html', plano=plano)

@app.route(f'{ADMIN_URL_PREFIX}/planos/<int:plano_id>/excluir', methods=['POST'])
@login_required
def excluir_plano(plano_id):
    try:
        plano = Plano.query.get_or_404(plano_id)
        plano.ativo = False
        db.session.commit()
        flash(f'Plano "{plano.nome}" excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao excluir plano: {e}")
        flash('Erro ao excluir plano.', 'error')
    
    return redirect(url_for('admin_planos'))

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
            flash('Configurações atualizadas com sucesso!', 'success')
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao atualizar configurações: {e}")
            flash('Erro ao atualizar configurações.', 'error')
    
    configs = get_configs()
    return render_template('admin/configuracoes.html', configs=configs)

# ========================================
# UTILITÁRIOS
# ========================================

def get_configs():
    """Retorna configurações sanitizadas"""
    try:
        configuracoes_db = Configuracao.query.all()
        configs = {}
        for config in configuracoes_db:
            configs[config.chave] = bleach.clean(config.valor)
        return configs
    except Exception as e:
        app.logger.error(f"Erro ao buscar configurações: {e}")
        # Retorna valores padrão se a tabela não existir
        return {
            'SITE_NAME': 'NetFyber',
            'SITE_DESCRIPTION': 'Plataforma de Testes de Velocidade',
            'MAINTENANCE_MODE': 'false'
        }

@app.route('/api/planos')
def api_planos():
    planos_data = Plano.query.filter_by(ativo=True).order_by(Plano.ordem_exibicao).all()
    planos_list = []
    for plano in planos_data:
        planos_list.append({
            'id': plano.id,
            'nome': plano.nome,
            'preco': plano.preco,
            'velocidade': plano.velocidade,
            'features': plano.get_features_list(),
            'recomendado': plano.recomendado
        })
    return jsonify(planos_list)

@app.route('/api/blog/posts')
def api_blog_posts():
    try:
        posts = Post.query.filter_by(ativo=True).order_by(Post.data_publicacao.desc()).all()
        posts_list = []
        for post in posts:
            posts_list.append({
                'id': post.id,
                'titulo': post.titulo,
                'resumo': post.resumo,
                'categoria': post.categoria,
                'imagem': post.get_imagem_url(),
                'link_materia': post.link_materia,
                'data_publicacao': post.get_data_formatada(),
                'conteudo': post.conteudo
            })
        return jsonify(posts_list)
    except Exception as e:
        print(f"Erro na API /api/blog/posts: {e}")
        return jsonify([])

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy', 
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0'
    })

# ========================================
# HANDLERS DE ERRO
# ========================================

@app.errorhandler(404)
def pagina_nao_encontrada(error):
    return render_template('public/404.html', configs=get_configs()), 404

@app.errorhandler(403)
def acesso_negado(error):
    print(f"Acesso negado: {request.remote_addr} - {request.path}")
    return render_template('public/403.html', configs=get_configs()), 403

@app.errorhandler(500)
def erro_servidor(error):
    print(f"Erro interno do servidor: {error}")
    return render_template('public/500.html', configs=get_configs()), 500

# ========================================
# INICIALIZAÇÃO DO BANCO DE DADOS
# ========================================

def init_database():
    """Inicializa o banco de dados automaticamente"""
    try:
        with app.app_context():
            # Cria todas as tabelas
            db.create_all()
            print("✅ Tabelas criadas/verificadas com sucesso!")
            
            # Cria usuário admin se não existir
            if AdminUser.query.filter_by(username=ADMIN_USERNAME).first() is None:
                admin_user = AdminUser(
                    username=ADMIN_USERNAME, 
                    email=ADMIN_EMAIL
                )
                admin_user.set_password(ADMIN_PASSWORD)
                db.session.add(admin_user)
                db.session.commit()
                print(f"✅ Usuário administrativo '{ADMIN_USERNAME}' criado com sucesso!")
            
            # Adiciona configurações padrão se não existirem
            configs_padrao = {
                'telefone_contato': '(63) 8494-1778',
                'email_contato': 'contato@netfyber.com',
                'endereco': 'AV. Tocantins – 934, Centro – Sítio Novo – TO<br>Axixá TO / Juverlândia / São Pedro / Folha Seca / Morada Nova / Santa Luzia / Boa Esperança',
                'horario_segunda_sexta': '08h às 18h',
                'horario_sabado': '08h às 13h',
                'whatsapp_numero': '556384941778',
                'instagram_url': 'https://www.instagram.com/netfybertelecom',
                'facebook_url': '#',
                'hero_imagem': 'images/familia.png',
                'hero_titulo': 'Internet de Alta Velocidade',
                'hero_subtitulo': 'Conecte sua família ao futuro com a NetFyber Telecom'
            }
            
            for chave, valor in configs_padrao.items():
                if Configuracao.query.filter_by(chave=chave).first() is None:
                    config = Configuracao(chave=chave, valor=valor)
                    db.session.add(config)
                    print(f"✅ Configuração '{chave}' adicionada.")
            
            # Adiciona post de exemplo se não houver posts
            if Post.query.count() == 0:
                posts_exemplo = [
                    Post(
                        titulo='IA generativa cresce fortemente, mas requer estratégia bem pensada',
                        conteudo='De acordo com executivos do Itaú e do Banco do Brasil, a inteligência artificial generativa tem grande potencial disruptivo, mas exige investimento significativo e planejamento estratégico — "não basta usar por usar", segundo Marisa Reghini, do BB.\n\n**Muitos bancos preparam uso de "agentes de IA" para automatizar tarefas complexas.**\n<a href="https://www.ibm.com/br-pt/news" target="_blank">IBM Brasil Newsroom</a>\n\n**Apesar do entusiasmo, existe cautela sobre os custos e riscos da adoção.**\n<a href="https://veja.abril.com.br" target="_blank">VEJA</a>',
                        resumo='IA generativa cresce fortemente, mas requer estratégia bem pensada. De acordo com executivos do Itaú e do Banco do Brasil...',
                        categoria='tecnologia',
                        imagem='default.jpg',
                        link_materia='https://www.valor.com.br/tecnologia/noticia/ia-generativa-cresce-fortemente-mas-requer-estrategia',
                        data_publicacao=datetime(2025, 11, 1)
                    )
                ]
                
                for post in posts_exemplo:
                    db.session.add(post)
                
                print("✅ Posts de exemplo adicionados com sucesso!")
            
            db.session.commit()
            print("🎉 Banco de dados inicializado com sucesso!")
            
    except Exception as e:
        print(f"⚠️ Erro ao inicializar banco de dados: {e}")

# ========================================
# INICIALIZAÇÃO DA APLICAÇÃO
# ========================================

# Inicializa o banco de dados quando o aplicativo começar
with app.app_context():
    init_database()

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)