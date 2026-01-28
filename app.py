import os
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

# ========================================
# CONFIGURAÇÃO DA APLICAÇÃO
# ========================================

app = Flask(__name__)

# Configurações de variáveis de ambiente
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Configuração do banco de dados - CORREÇÃO CRÍTICA PARA RENDER
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///netfyber.db')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Forçar SSL no PostgreSQL (necessário para Render)
if DATABASE_URL and DATABASE_URL.startswith("postgresql://") and os.environ.get('FLASK_ENV') == 'production':
    if '?' in DATABASE_URL:
        DATABASE_URL += '&sslmode=require'
    else:
        DATABASE_URL += '?sslmode=require'

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 300,
    'pool_pre_ping': True,
    'connect_args': {
        'connect_timeout': 10,
        'application_name': 'netfyber-telecom'
    }
}

# Configurações de segurança
ADMIN_URL_PREFIX = os.environ.get('ADMIN_URL_PREFIX', '/gestao-exclusiva-netfyber')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)

# Configuração de upload LOCAL
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads', 'blog')
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8MB

# Configurações Cloudflare R2 (para produção)
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

# Headers de segurança
@app.after_request
def secure_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if os.environ.get('FLASK_ENV') == 'production':
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# ========================================
# FUNÇÕES DE ARMAZENAMENTO DUAL (LOCAL + R2)
# ========================================

def allowed_file(filename):
    """Verifica se o arquivo tem uma extensão permitida"""
    if not filename or '.' not in filename:
        return False
    return filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_image_local(file):
    """Salva imagem localmente (desenvolvimento)"""
    if not file or file.filename == '':
        return None
    
    if not allowed_file(file.filename):
        return None
    
    try:
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            print(f"✅ Imagem salva localmente: {filename}")
            return filename
            
    except Exception as e:
        print(f"❌ Erro ao salvar imagem localmente: {e}")
    
    return None

def save_image_r2(file):
    """Salva imagem no Cloudflare R2 (produção)"""
    if not file or file.filename == '':
        return None
    
    if not allowed_file(file.filename):
        return None
    
    try:
        import boto3
        from botocore.exceptions import ClientError
        
        # Configurar cliente S3 para Cloudflare R2
        s3_client = boto3.client(
            's3',
            endpoint_url=current_app.config.get('R2_ENDPOINT_URL'),
            aws_access_key_id=current_app.config.get('R2_ACCESS_KEY_ID'),
            aws_secret_access_key=current_app.config.get('R2_SECRET_ACCESS_KEY'),
            region_name='auto'
        )
        
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        bucket_name = current_app.config.get('R2_BUCKET')
        
        # Determina content type
        content_type = f'image/{ext}'
        if ext == 'jpg':
            content_type = 'image/jpeg'
        
        s3_client.upload_fileobj(
            file,
            bucket_name,
            filename,
            ExtraArgs={
                'ContentType': content_type
            }
        )
        
        print(f"✅ Imagem enviada para Cloudflare R2: {filename}")
        return filename
        
    except Exception as e:
        print(f"❌ Erro ao enviar para R2: {e}")
        return None

def save_blog_image(file):
    """Salva imagem do blog usando método apropriado"""
    if not file or file.filename == '':
        return None
    
    if current_app.config.get('R2_ENABLED'):
        result = save_image_r2(file)
        if result:
            return result
    
    # Fallback para armazenamento local
    return save_image_local(file)

def delete_image_local(filename):
    """Exclui imagem localmente"""
    if not filename or filename == 'default.jpg':
        return False
    
    try:
        upload_folder = current_app.config['UPLOAD_FOLDER']
        file_path = os.path.join(upload_folder, filename)
        
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"✅ Imagem local excluída: {filename}")
            return True
    except Exception as e:
        print(f"❌ Erro ao excluir imagem local: {e}")
    
    return False

def delete_image_r2(filename):
    """Exclui imagem do Cloudflare R2"""
    if not filename or filename == 'default.jpg':
        return False
    
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
        print(f"✅ Imagem excluída do R2: {filename}")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao excluir do R2: {e}")
        return False

def delete_blog_image(filename):
    """Exclui imagem do blog usando método apropriado"""
    if not filename or filename == 'default.jpg':
        return False
    
    if current_app.config.get('R2_ENABLED'):
        return delete_image_r2(filename)
    else:
        return delete_image_local(filename)

def get_image_url(filename):
    """Retorna URL da imagem baseada no ambiente"""
    if not filename or filename == 'default.jpg':
        return "/static/images/blog/default.jpg"
    
    # Se R2 habilitado, usa URL do Cloudflare R2
    if current_app.config.get('R2_ENABLED'):
        public_url_base = current_app.config.get('R2_PUBLIC_URL', '').rstrip('/')
        bucket_name = current_app.config.get('R2_BUCKET')
        
        if public_url_base:
            # Formato Cloudflare R2: https://pub-<account-id>.r2.dev/<bucket-name>/<filename>
            return f"{public_url_base}/{bucket_name}/{filename}"
    
    # Fallback para URL local
    return f"/static/uploads/blog/{filename}"

# ========================================
# FUNÇÕES DE FORMATAÇÃO INTELIGENTE
# ========================================

def process_markdown(content):
    """Processa formatação estilo markdown"""
    if not content:
        return ""
    
    lines = content.split('\n')
    processed_lines = []
    in_list = False
    
    for line in lines:
        line = line.rstrip()
        
        if not line:
            if in_list:
                processed_lines.append('</ul>')
                in_list = False
            processed_lines.append('<br>')
            continue
        
        # Processar listas
        if line.strip().startswith('- ') or line.strip().startswith('* '):
            if not in_list:
                processed_lines.append('<ul>')
                in_list = True
            list_item = line.strip()[2:].strip()
            list_item = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', list_item)
            processed_lines.append(f'<li>{list_item}</li>')
            continue
        else:
            if in_list:
                processed_lines.append('</ul>')
                in_list = False
        
        # Processar títulos
        if line.strip().startswith('### '):
            title = line.strip()[4:].strip()
            processed_lines.append(f'<h3>{title}</h3>')
        elif line.strip().startswith('## '):
            title = line.strip()[3:].strip()
            processed_lines.append(f'<h2>{title}</h2>')
        elif line.strip().startswith('# '):
            title = line.strip()[2:].strip()
            processed_lines.append(f'<h1>{title}</h1>')
        else:
            line = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line)
            processed_lines.append(line + '<br>')
    
    if in_list:
        processed_lines.append('</ul>')
    
    return '\n'.join(processed_lines)

def sanitize_html(content):
    """Sanitização segura de HTML"""
    if not content:
        return ""
    
    # Primeiro processar o markdown
    html_content = process_markdown(content)
    
    # Tags permitidas
    allowed_tags = [
        'p', 'br', 'strong', 'em', 'b', 'i', 'u', 'a',
        'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'blockquote', 'img', 'span', 'div'
    ]
    
    # Atributos permitidos
    allowed_attributes = {
        'a': ['href', 'target', 'rel', 'title', 'class'],
        'img': ['src', 'alt', 'title', 'width', 'height', 'class', 'style'],
        '*': ['class', 'style']
    }
    
    # Sanitizar
    sanitized = bleach.clean(
        html_content,
        tags=allowed_tags,
        attributes=allowed_attributes,
        strip=True,
        strip_comments=True
    )
    
    # Garantir que links externos tenham target="_blank" e rel="noopener noreferrer"
    def add_link_attributes(attrs, new):
        href = attrs.get((None, 'href'), '')
        if href and href.startswith(('http://', 'https://')):
            attrs[(None, 'target')] = '_blank'
            attrs[(None, 'rel')] = 'noopener noreferrer'
        return attrs
    
    sanitized = bleach.linkify(sanitized, callbacks=[add_link_attributes])
    
    return sanitized

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        if len(password) < 8:
            raise ValueError("Senha deve ter pelo menos 8 caracteres")
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
    link_materia = db.Column(db.String(500), nullable=False)
    data_publicacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_conteudo_html(self):
        """Retorna o conteúdo formatado com a formatação inteligente"""
        if not self.conteudo:
            return "<p>Conteúdo não disponível.</p>"
        return sanitize_html(self.conteudo)

    def get_data_formatada(self):
        return self.data_publicacao.strftime('%d/%m/%Y')

    def get_imagem_url(self):
        """Retorna a URL da imagem usando a função get_image_url"""
        return get_image_url(self.imagem)

@login_manager.user_loader
def load_user(user_id):
    return AdminUser.query.get(int(user_id))

# ========================================
# FUNÇÕES AUXILIARES
# ========================================

def get_configs():
    """Retorna configurações do site"""
    try:
        configuracoes_db = Configuracao.query.all()
        configs = {}
        for config in configuracoes_db:
            configs[config.chave] = bleach.clean(config.valor)
        return configs
    except Exception as e:
        print(f"Erro ao carregar configurações: {e}")
        return {}

# ========================================
# SINCRONIZAÇÃO DO ADMIN
# ========================================

def sync_admin_from_env():
    """Sincroniza usuário admin a partir das variáveis de ambiente"""
    admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
    admin_password = os.environ.get('ADMIN_PASSWORD', 'Teste123!')
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@netfyber.com')
    
    if not admin_username or not admin_password:
        print("⚠️ ADMIN_USERNAME ou ADMIN_PASSWORD não definidos.")
        return
    
    try:
        user = AdminUser.query.filter_by(username=admin_username).first()
        
        if user:
            user.set_password(admin_password)
            user.email = admin_email
            print(f"✅ Admin {admin_username} atualizado.")
        else:
            new_admin = AdminUser(username=admin_username, email=admin_email)
            new_admin.set_password(admin_password)
            db.session.add(new_admin)
            print(f"✅ Admin {admin_username} criado.")
        
        db.session.commit()
    except Exception as e:
        print(f"❌ Erro ao sincronizar admin: {e}")

# ========================================
# INICIALIZAÇÃO DO BANCO DE DADOS
# ========================================

_db_initialized = False

def init_database():
    """Inicializa o banco de dados e configurações padrão"""
    global _db_initialized
    
    if _db_initialized:
        return
    
    try:
        print("🔄 Tentando criar tabelas...")
        db.create_all()
        
        # Sincronizar admin do ambiente
        sync_admin_from_env()
        
        # Verificar se há configurações
        if Configuracao.query.count() == 0:
            print("⚙️ Criando configurações padrão...")
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
                config = Configuracao(chave=chave, valor=valor)
                db.session.add(config)
            
            db.session.commit()
        
        _db_initialized = True
        print("✅ Banco de dados inicializado!")
        
    except Exception as e:
        print(f"❌ Erro ao inicializar banco: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        # Não levantamos a exceção para evitar que a aplicação quebre completamente

@app.before_request
def before_request():
    """Inicializa o banco de dados antes da primeira requisição"""
    try:
        init_database()
    except Exception as e:
        print(f"⚠️ Aviso: Não foi possível inicializar o banco de dados: {e}")
        # Podemos continuar a execução mesmo sem o banco de dados para páginas que não dependem dele

# ========================================
# ROTAS PÚBLICAS
# ========================================

@app.route('/')
def index():
    try:
        configs = get_configs()
    except Exception:
        configs = {}
    return render_template('public/index.html', configs=configs)

@app.route('/planos')
def planos():
    try:
        planos_data = Plano.query.filter_by(ativo=True).order_by(Plano.ordem_exibicao).all()
    except Exception as e:
        print(f"Erro ao carregar planos: {e}")
        planos_data = []
    
    planos_formatados = []
    for plano in planos_data:
        planos_formatados.append({
            'nome': bleach.clean(plano.nome),
            'preco': bleach.clean(plano.preco),
            'features': [bleach.clean(f) for f in plano.get_features_list()],
            'recomendado': plano.recomendado
        })
    
    try:
        configs = get_configs()
    except Exception:
        configs = {}
        
    return render_template('public/planos.html', planos=planos_formatados, configs=configs)

@app.route('/blog')
def blog():
    try:
        posts = Post.query.filter_by(ativo=True).order_by(Post.data_publicacao.desc()).all()
    except Exception as e:
        print(f"Erro ao carregar posts: {e}")
        posts = []
    
    try:
        configs = get_configs()
    except Exception:
        configs = {}
    
    return render_template('public/blog.html', configs=configs, posts=posts)

@app.route('/velocimetro')
def velocimetro():
    try:
        configs = get_configs()
    except Exception:
        configs = {}
    return render_template('public/velocimetro.html', configs=configs)

@app.route('/sobre')
def sobre():
    try:
        configs = get_configs()
    except Exception:
        configs = {}
    return render_template('public/sobre.html', configs=configs)

# ========================================
# AUTENTICAÇÃO ADMIN
# ========================================

@app.route(f'{ADMIN_URL_PREFIX}/login', methods=['GET', 'POST'])
def admin_login():
    # Se o banco de dados não estiver inicializado, tenta inicializar
    try:
        init_database()
    except Exception as e:
        print(f"⚠️ Aviso: Não foi possível inicializar o banco de dados: {e}")
    
    if current_user.is_authenticated:
        return redirect(url_for('admin_planos'))
    
    if request.method == 'POST':
        username = bleach.clean(request.form.get('username', '').strip())
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Credenciais inválidas.', 'error')
            return render_template('auth/login.html')
        
        try:
            user = AdminUser.query.filter_by(username=username, is_active=True).first()
            
            if user:
                try:
                    if user.check_password(password):
                        login_user(user, remember=False)
                        user.last_login = datetime.utcnow()
                        db.session.commit()
                        flash('Login realizado com sucesso!', 'success')
                        return redirect(url_for('admin_planos'))
                    else:
                        flash('Usuário ou senha inválidos.', 'error')
                except Exception as e:
                    flash(f'Erro ao fazer login: {str(e)}', 'error')
            else:
                flash('Usuário ou senha inválidos.', 'error')
        except Exception as e:
            flash(f'Erro ao acessar o banco de dados: {str(e)}', 'error')
    
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
    try:
        posts = Post.query.filter_by(ativo=True).order_by(Post.data_publicacao.desc()).all()
    except Exception as e:
        print(f"Erro ao carregar posts: {e}")
        posts = []
        flash('Erro ao carregar posts do blog.', 'error')
    
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
            
            # Validar URL
            link_materia = request.form['link_materia'].strip()
            if not validate_url(link_materia):
                flash('URL da matéria inválida.', 'error')
                return redirect(request.url)
            
            # Processar imagem
            imagem_filename = 'default.jpg'
            
            if 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename != '':
                    uploaded_filename = save_blog_image(file)
                    if uploaded_filename:
                        imagem_filename = uploaded_filename
            
            # Validar data
            try:
                data_publicacao = datetime.strptime(request.form['data_publicacao'], '%d/%m/%Y')
            except ValueError:
                flash('Formato de data inválido. Use DD/MM/AAAA.', 'error')
                return redirect(request.url)
            
            # Criar resumo
            conteudo_texto = re.sub(r'<[^>]+>', '', request.form['conteudo'])
            resumo = conteudo_texto[:150] + '...' if len(conteudo_texto) > 150 else conteudo_texto
            
            # Criar post
            novo_post = Post(
                titulo=bleach.clean(request.form['titulo']),
                conteudo=request.form['conteudo'],
                resumo=bleach.clean(resumo),
                categoria=bleach.clean(request.form['categoria']),
                imagem=imagem_filename,
                link_materia=link_materia,
                data_publicacao=data_publicacao
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
    try:
        post = Post.query.get_or_404(post_id)
    except Exception as e:
        flash(f'Erro ao carregar post: {str(e)}', 'error')
        return redirect(url_for('admin_blog'))
    
    if request.method == 'POST':
        try:
            # Atualizar imagem se fornecida
            if 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename != '':
                    uploaded_filename = save_blog_image(file)
                    if uploaded_filename:
                        # Excluir imagem antiga
                        if post.imagem and post.imagem != 'default.jpg':
                            delete_blog_image(post.imagem)
                        
                        post.imagem = uploaded_filename
            
            # Validar URL
            link_materia = request.form['link_materia'].strip()
            if not validate_url(link_materia):
                flash('URL da matéria inválida.', 'error')
                return redirect(request.url)
            
            # Validar data
            try:
                data_publicacao = datetime.strptime(request.form['data_publicacao'], '%d/%m/%Y')
            except ValueError:
                flash('Formato de data inválido. Use DD/MM/AAAA.', 'error')
                return redirect(request.url)
            
            # Criar resumo
            conteudo_texto = re.sub(r'<[^>]+>', '', request.form['conteudo'])
            resumo = conteudo_texto[:150] + '...' if len(conteudo_texto) > 150 else conteudo_texto
            
            # Atualizar post
            post.titulo = bleach.clean(request.form['titulo'])
            post.conteudo = request.form['conteudo']
            post.resumo = bleach.clean(resumo)
            post.categoria = bleach.clean(request.form['categoria'])
            post.link_materia = link_materia
            post.data_publicacao = data_publicacao
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
            delete_blog_image(post.imagem)
        
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
    try:
        planos_data = Plano.query.filter_by(ativo=True).order_by(Plano.ordem_exibicao).all()
    except Exception as e:
        print(f"Erro ao carregar planos: {e}")
        planos_data = []
        flash('Erro ao carregar planos.', 'error')
    
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
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao adicionar plano: {str(e)}', 'error')
    
    return render_template('admin/plano_form.html')

@app.route(f'{ADMIN_URL_PREFIX}/planos/<int:plano_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_plano(plano_id):
    try:
        plano = Plano.query.get_or_404(plano_id)
    except Exception as e:
        flash(f'Erro ao carregar plano: {str(e)}', 'error')
        return redirect(url_for('admin_planos'))
    
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
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar plano: {str(e)}', 'error')
    
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
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar configurações: {str(e)}', 'error')
    
    try:
        configs = get_configs()
    except Exception:
        configs = {}
        flash('Erro ao carregar configurações.', 'error')
    
    return render_template('admin/configuracoes.html', configs=configs)

# ========================================
# UTILITÁRIOS E ERROS
# ========================================

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

@app.errorhandler(404)
def pagina_nao_encontrada(error):
    try:
        configs = get_configs()
    except Exception:
        configs = {}
    return render_template('public/404.html', configs=configs), 404

@app.errorhandler(403)
def acesso_negado(error):
    try:
        configs = get_configs()
    except Exception:
        configs = {}
    return render_template('public/403.html', configs=configs), 403

@app.errorhandler(500)
def erro_servidor(error):
    try:
        configs = get_configs()
    except Exception:
        configs = {}
    return render_template('public/500.html', configs=configs), 500

# ========================================
# PONTO DE ENTRADA PRINCIPAL
# ========================================

if __name__ == '__main__':
    # Para desenvolvimento local
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get('FLASK_ENV') != 'production'
    
    # Garantir que o diretório de uploads exista
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Log de configuração
    print(f"🔧 Ambiente: {os.environ.get('FLASK_ENV', 'development')}")
    print(f"📁 Upload local: {app.config['UPLOAD_FOLDER']}")
    print(f"☁️ Cloudflare R2: {'HABILITADO' if app.config['R2_ENABLED'] else 'DESABILITADO'}")
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)