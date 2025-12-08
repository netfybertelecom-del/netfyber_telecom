import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import bleach
import re
from urllib.parse import urlparse
import secrets

# ========================================
# CONFIGURAÇÃO DA APLICAÇÃO
# ========================================

app = Flask(__name__)

# Configurações de variáveis de ambiente
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Configuração do banco de dados
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///netfyber.db')
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configurações de segurança
ADMIN_URL_PREFIX = os.environ.get('ADMIN_URL_PREFIX', '/gestao-exclusiva-netfyber')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)

# Configuração de upload
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads', 'blog')
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8MB

# Configurações S3 (Cloudflare R2 ou AWS S3)
app.config['S3_ENABLED'] = os.environ.get('S3_ENABLED', 'false').lower() == 'true'
app.config['S3_BUCKET'] = os.environ.get('S3_BUCKET')
app.config['S3_REGION'] = os.environ.get('S3_REGION')
app.config['S3_ENDPOINT_URL'] = os.environ.get('S3_ENDPOINT_URL')
app.config['S3_ACCESS_KEY_ID'] = os.environ.get('S3_ACCESS_KEY_ID')
app.config['S3_SECRET_ACCESS_KEY'] = os.environ.get('S3_SECRET_ACCESS_KEY')

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

# Headers de segurança
@app.after_request
def secure_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self' https: data: 'unsafe-inline';"
    if os.environ.get('FLASK_ENV') == 'production':
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

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
        if len(password) < 8:
            raise ValueError("Senha deve ter pelo menos 8 caracteres")
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if self.locked_until and datetime.utcnow() < self.locked_until:
            raise ValueError("Conta temporariamente bloqueada. Tente novamente mais tarde.")
        
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
        if not self.features:
            return []
        return [bleach.clean(f.strip()) for f in self.features.split('\n') if f.strip()]

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
    imagem = db.Column(db.String(500), default='default.jpg')
    imagem_storage_type = db.Column(db.String(20), default='local')  # 'local' ou 's3'
    link_materia = db.Column(db.String(500), nullable=False)
    data_publicacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_conteudo_html(self):
        if not self.conteudo:
            return "<p>Conteúdo não disponível.</p>"
        
        # Sanitizar HTML
        allowed_tags = ['p', 'br', 'strong', 'em', 'b', 'i', 'u', 'a', 'ul', 'ol', 'li', 
                       'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'img', 'span', 'div']
        
        html = bleach.clean(
            self.conteudo,
            tags=allowed_tags,
            attributes={'a': ['href', 'target', 'rel'], 'img': ['src', 'alt']},
            strip=True
        )
        
        # Adicionar target="_blank" a links externos
        html = bleach.linkify(html, callbacks=[lambda attrs, _: add_target_blank(attrs)])
        return html

    def get_data_formatada(self):
        return self.data_publicacao.strftime('%d/%m/%Y')

    def get_imagem_url(self):
        if self.imagem and self.imagem != 'default.jpg':
            if self.imagem_storage_type == 's3':
                return self.imagem
            else:
                return f"/static/uploads/blog/{self.imagem}"
        return "/static/images/blog/default.jpg"

def add_target_blank(attrs):
    if (None, 'href') in attrs:
        attrs[(None, 'target')] = '_blank'
        attrs[(None, 'rel')] = 'noopener noreferrer'
    return attrs

@login_manager.user_loader
def load_user(user_id):
    return AdminUser.query.get(int(user_id))

# ========================================
# SINCRONIZAÇÃO DO ADMIN
# ========================================

def sync_admin_from_env():
    """Sincroniza usuário admin a partir das variáveis de ambiente"""
    admin_username = os.environ.get('ADMIN_USERNAME')
    admin_password = os.environ.get('ADMIN_PASSWORD')
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@netfyber.com')
    
    if not admin_username or not admin_password:
        print("⚠️ ADMIN_USERNAME ou ADMIN_PASSWORD não definidos. Pulando criação de admin.")
        return
    
    user = AdminUser.query.filter_by(username=admin_username).first()
    
    if user:
        user.set_password(admin_password)
        user.email = admin_email
        db.session.commit()
        print(f"✅ Admin {admin_username} atualizado.")
    else:
        new_admin = AdminUser(username=admin_username, email=admin_email)
        new_admin.set_password(admin_password)
        db.session.add(new_admin)
        db.session.commit()
        print(f"✅ Admin {admin_username} criado.")

# ========================================
# FUNÇÕES DE UTILIDADE
# ========================================

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file):
    """Salva arquivo usando storage.py"""
    try:
        from storage import save_file
        return save_file(file)
    except ImportError:
        # Fallback local
        if file and allowed_file(file.filename):
            filename = f"{uuid.uuid4().hex}.{file.filename.rsplit('.', 1)[1].lower()}"
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            return {'filename': filename, 'storage_type': 'local', 'url': f"/static/uploads/blog/{filename}"}
    return None

def delete_uploaded_file(filename, storage_type='local'):
    """Exclui arquivo usando storage.py"""
    try:
        if storage_type == 's3':
            from storage import delete_file_s3
            return delete_file_s3(filename)
        else:
            from storage import delete_file_local
            return delete_file_local(filename)
    except Exception:
        return False

def get_configs():
    """Retorna configurações do site"""
    try:
        configuracoes_db = Configuracao.query.all()
        configs = {}
        for config in configuracoes_db:
            configs[config.chave] = bleach.clean(config.valor)
        return configs
    except Exception:
        return {}

# ========================================
# ROTAS PÚBLICAS
# ========================================

@app.route('/')
def index():
    return render_template('public/index.html', configs=get_configs())

@app.route('/planos')
def planos():
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

@app.route('/blog')
def blog():
    posts = Post.query.filter_by(ativo=True).order_by(Post.data_publicacao.desc()).all()
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
                    return redirect(url_for('admin_planos'))
                else:
                    flash('Usuário ou senha inválidos.', 'error')
            except ValueError as e:
                flash(str(e), 'error')
        else:
            flash('Usuário ou senha inválidos.', 'error')
    
    return render_template('auth/login.html')

@app.route(f'{ADMIN_URL_PREFIX}/logout')
@login_required
def admin_logout():
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
            # Validação básica
            required_fields = ['titulo', 'conteudo', 'categoria', 'link_materia']
            for field in required_fields:
                if not request.form.get(field):
                    flash(f'O campo {field} é obrigatório.', 'error')
                    return redirect(request.url)
            
            # Processar imagem
            imagem_filename = 'default.jpg'
            imagem_storage_type = 'local'
            
            if 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename != '':
                    result = save_uploaded_file(file)
                    if result:
                        imagem_filename = result['filename']
                        imagem_storage_type = result['storage_type']
            
            # Criar resumo
            conteudo_limpo = re.sub(r'<[^>]+>', '', request.form['conteudo'])
            conteudo_limpo = re.sub(r'\*\*.*?\*\*', '', conteudo_limpo)
            resumo = conteudo_limpo[:150] + '...' if len(conteudo_limpo) > 150 else conteudo_limpo
            
            # Criar post
            novo_post = Post(
                titulo=bleach.clean(request.form['titulo']),
                conteudo=bleach.clean(request.form['conteudo']),
                resumo=bleach.clean(resumo),
                categoria=bleach.clean(request.form['categoria']),
                imagem=imagem_filename,
                imagem_storage_type=imagem_storage_type,
                link_materia=request.form['link_materia'],
                data_publicacao=datetime.strptime(request.form['data_publicacao'], '%d/%m/%Y')
            )
            
            db.session.add(novo_post)
            db.session.commit()
            
            flash(f'Post "{novo_post.titulo}" adicionado com sucesso!', 'success')
            return redirect(url_for('admin_blog'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao adicionar post: {str(e)}', 'error')
    
    return render_template('admin/post_form.html', post=None, data_hoje=datetime.now().strftime('%d/%m/%Y'))

@app.route(f'{ADMIN_URL_PREFIX}/blog/<int:post_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_post(post_id):
    post = Post.query.get_or_404(post_id)
    
    if request.method == 'POST':
        try:
            # Atualizar imagem se fornecida
            if 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename != '':
                    result = save_uploaded_file(file)
                    if result:
                        # Excluir imagem antiga
                        if post.imagem and post.imagem != 'default.jpg':
                            delete_uploaded_file(post.imagem, post.imagem_storage_type)
                        
                        post.imagem = result['filename']
                        post.imagem_storage_type = result['storage_type']
            
            # Atualizar outros campos
            post.titulo = bleach.clean(request.form['titulo'])
            post.conteudo = bleach.clean(request.form['conteudo'])
            post.categoria = bleach.clean(request.form['categoria'])
            post.link_materia = request.form['link_materia']
            post.data_publicacao = datetime.strptime(request.form['data_publicacao'], '%d/%m/%Y')
            post.updated_at = datetime.utcnow()
            
            db.session.commit()
            flash('Post atualizado com sucesso!', 'success')
            return redirect(url_for('admin_blog'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar post: {str(e)}', 'error')
    
    return render_template('admin/post_form.html', post=post, data_hoje=post.get_data_formatada())

@app.route(f'{ADMIN_URL_PREFIX}/blog/<int:post_id>/excluir', methods=['POST'])
@login_required
def excluir_post(post_id):
    try:
        post = Post.query.get_or_404(post_id)
        
        # Excluir imagem se não for default
        if post.imagem and post.imagem != 'default.jpg':
            delete_uploaded_file(post.imagem, post.imagem_storage_type)
        
        post.ativo = False
        db.session.commit()
        flash(f'Post "{post.titulo}" excluído com sucesso!', 'success')
    except Exception:
        db.session.rollback()
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
                nome=bleach.clean(request.form['nome']),
                preco=bleach.clean(request.form['preco']),
                features=bleach.clean(request.form['features']),
                velocidade=bleach.clean(request.form.get('velocidade', '')),
                recomendado='recomendado' in request.form
            )
            db.session.add(novo_plano)
            db.session.commit()
            flash(f'Plano "{novo_plano.nome}" adicionado com sucesso!', 'success')
            return redirect(url_for('admin_planos'))
        except Exception:
            db.session.rollback()
            flash('Erro ao adicionar plano.', 'error')
    
    return render_template('admin/plano_form.html')

@app.route(f'{ADMIN_URL_PREFIX}/planos/<int:plano_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_plano(plano_id):
    plano = Plano.query.get_or_404(plano_id)
    
    if request.method == 'POST':
        try:
            plano.nome = bleach.clean(request.form['nome'])
            plano.preco = bleach.clean(request.form['preco'])
            plano.features = bleach.clean(request.form['features'])
            plano.velocidade = bleach.clean(request.form.get('velocidade', ''))
            plano.recomendado = 'recomendado' in request.form
            
            db.session.commit()
            flash('Plano atualizado com sucesso!', 'success')
            return redirect(url_for('admin_planos'))
        except Exception:
            db.session.rollback()
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
    except Exception:
        db.session.rollback()
        flash('Erro ao excluir plano.', 'error')
    
    return redirect(url_for('admin_planos'))

@app.route(f'{ADMIN_URL_PREFIX}/configuracoes', methods=['GET', 'POST'])
@login_required
def admin_configuracoes():
    if request.method == 'POST':
        try:
            for chave, valor in request.form.items():
                if chave != 'csrf_token' and valor.strip():
                    config = Configuracao.query.filter_by(chave=chave).first()
                    if config:
                        config.valor = bleach.clean(valor.strip())
                    else:
                        config = Configuracao(chave=chave, valor=bleach.clean(valor.strip()))
                        db.session.add(config)
            db.session.commit()
            flash('Configurações atualizadas com sucesso!', 'success')
        except Exception:
            db.session.rollback()
            flash('Erro ao atualizar configurações.', 'error')
    
    configs = get_configs()
    return render_template('admin/configuracoes.html', configs=configs)

# ========================================
# UTILITÁRIOS E ERROS
# ========================================

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

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
# INICIALIZAÇÃO
# ========================================

def init_database():
    """Inicializa o banco de dados e configurações padrão"""
    with app.app_context():
        db.create_all()
        print("✅ Tabelas criadas/verificadas com sucesso!")
        
        # Sincronizar admin do ambiente
        sync_admin_from_env()
        
        # Configurações padrão
        configs_padrao = {
            'telefone_contato': '(63) 8494-1778',
            'email_contato': 'contato@netfyber.com',
            'endereco': 'AV. Tocantins – 934, Centro – Sítio Novo – TO<br>Axixá TO / Juverlândia / São Pedro / Folha Seca / Morada Nova / Santa Luzia / Boa Esperança',
            'horario_segunda_sexta': '08h às 18h',
            'horario_sabado': '08h às 13h',
            'whatsapp_numero': '556384941778',
            'instagram_url': 'https://www.instagram.com/netfybertelecom',
            'hero_imagem': 'images/familia.png',
            'hero_titulo': 'Internet de Alta Velocidade',
            'hero_subtitulo': 'Conecte sua família ao futuro com a NetFyber Telecom'
        }
        
        for chave, valor in configs_padrao.items():
            if Configuracao.query.filter_by(chave=chave).first() is None:
                config = Configuracao(chave=chave, valor=valor)
                db.session.add(config)
        
        db.session.commit()
        print("🎉 Banco de dados inicializado com sucesso!")

# Inicializar banco de dados
with app.app_context():
    init_database()

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)