from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import uuid
import re
import bleach
from bleach.linkifier import Linker
from urllib.parse import urlparse
import html
import os
from urllib.parse import urlparse

# Configurações específicas para Render
if 'RENDER' in os.environ:
    print("🚀 Ambiente Render detectado")
    
    # Forçar algumas configurações no Render
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_recycle': 300,
        'pool_pre_ping': True,
    }
app = Flask(__name__)

# ========================================
# CONFIGURAÇÕES BÁSICAS
# ========================================

SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:102030@localhost/testenet1')
ADMIN_URL_PREFIX = os.environ.get('ADMIN_URL_PREFIX', '/gestao-exclusiva-netfyber')
ADMIN_IPS = os.environ.get('ADMIN_IPS', '127.0.0.1').split(',')
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

db = SQLAlchemy(app)

# ========================================
# FUNÇÕES DE FORMATAÇÃO INTELIGENTE SIMPLIFICADA
# ========================================

def formatar_conteudo_inteligente(conteudo):
    """
    Formata conteúdo de forma simples e eficiente:
    1. **negrito** → <strong>negrito</strong>
    2. Quebras de linha → <br>
    3. Links HTML são mantidos com segurança
    4. Listas com - → <ul><li>
    
    Esta função é ALINHADA com o JavaScript do front-end
    """
    if not conteudo:
        return ""
    
    # 1. Processar listas primeiro (manter estrutura)
    lines = conteudo.strip().split('\n')
    result_lines = []
    in_list = False
    
    for line in lines:
        line = line.rstrip()
        
        # Verificar se é item de lista
        if line.startswith('- ') or line.startswith('* '):
            if not in_list:
                result_lines.append('<ul>')
                in_list = True
            
            item_content = line[2:].strip()
            # Processar negrito dentro do item da lista
            item_content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', item_content)
            result_lines.append(f'<li>{item_content}</li>')
        else:
            if in_list:
                result_lines.append('</ul>')
                in_list = False
            
            if line:
                # Processar títulos ##
                if line.startswith('## '):
                    title = line[3:].strip()
                    result_lines.append(f'<h4>{title}</h4>')
                else:
                    # Processar negrito no texto normal
                    line = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line)
                    # Manter quebras de linha originais
                    result_lines.append(line)
            else:
                # Linha vazia → quebra de parágrafo
                result_lines.append('<br>')
    
    # Fechar lista se ainda aberta
    if in_list:
        result_lines.append('</ul>')
    
    # Juntar tudo mantendo estrutura
    html_content = '\n'.join(result_lines)
    
    # 2. Converter quebras de linha restantes para <br>
    # Mas NÃO converter dentro de listas
    def process_paragraphs(text):
        paragraphs = text.split('\n')
        result = []
        
        for para in paragraphs:
            if para.startswith('<ul>') or para.startswith('<li>') or para.startswith('</ul>') or para.startswith('<h4>') or para.startswith('</h4>'):
                result.append(para)
            elif para == '<br>':
                result.append(para)
            elif para:
                result.append(f'{para}<br>')
            else:
                result.append('<br>')
        
        return ''.join(result)
    
    html_content = process_paragraphs(html_content)
    
    # 3. Processar links HTML com segurança
    def add_link_attributes(attrs, new=False):
        href_key = (None, 'href')
        if href_key in attrs:
            href = attrs[href_key]
            if href.startswith(('http://', 'https://')):
                rel_parts = []
                if (None, 'rel') in attrs:
                    rel_parts = attrs[(None, 'rel')].split()
                
                if 'noopener' not in rel_parts:
                    rel_parts.append('noopener')
                if 'noreferrer' not in rel_parts:
                    rel_parts.append('noreferrer')
                
                attrs[(None, 'rel')] = ' '.join(rel_parts)
                attrs[(None, 'target')] = '_blank'
        
        return attrs
    
    # 4. Sanitizar HTML permitindo tags seguras
    allowed_tags = ['p', 'br', 'strong', 'em', 'b', 'i', 'u', 'a', 'ul', 'ol', 'li', 
                   'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span', 'div']
    
    allowed_attributes = {
        'a': ['href', 'title', 'target', 'rel', 'class'],
        '*': ['class']
    }
    
    # Primeiro linkify para processar URLs
    linker = Linker(callbacks=[add_link_attributes])
    html_content = linker.linkify(html_content)
    
    # Depois sanitizar
    conteudo_sanitizado = bleach.clean(
        html_content,
        tags=allowed_tags,
        attributes=allowed_attributes,
        strip=True,
        strip_comments=True
    )
    
    # 5. Corrigir múltiplos <br> consecutivos
    conteudo_sanitizado = re.sub(r'(<br>\s*){3,}', '<br><br>', conteudo_sanitizado)
    
    # 6. Remover <br> dentro de listas (se ainda houver)
    def clean_br_in_lists(match):
        content = match.group(0)
        # Remover <br> entre itens de lista
        content = re.sub(r'</li>\s*<br>\s*<li>', '</li><li>', content)
        # Remover <br> no início/fim dos itens
        content = re.sub(r'<li>\s*<br>\s*', '<li>', content)
        content = re.sub(r'\s*<br>\s*</li>', '</li>', content)
        return content
    
    conteudo_sanitizado = re.sub(r'<ul>.*?</ul>', clean_br_in_lists, conteudo_sanitizado, flags=re.DOTALL)
    
    return conteudo_sanitizado
    
    # 7. Sanitizar HTML permitindo apenas tags seguras
    allowed_tags = ['p', 'br', 'strong', 'em', 'b', 'i', 'u', 'a', 'ul', 'ol', 'li', 
                   'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span', 'div']
    
    allowed_attributes = {
        'a': ['href', 'title', 'target', 'rel', 'class'],
        '*': ['class']
    }
    
    # Sanitizar o HTML
    conteudo_sanitizado = bleach.clean(
        conteudo_formatado,
        tags=allowed_tags,
        attributes=allowed_attributes,
        strip=True,
        strip_comments=True
    )
    
    # 8. Processar links com atributos de segurança
    linker = Linker(callbacks=[add_link_attributes])
    conteudo_final = linker.linkify(conteudo_sanitizado)
    
    return conteudo_final

# ========================================
# SEGURANÇA
# ========================================

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'
login_manager.login_message = "Por favor, faça login para acessar esta página."
login_manager.login_message_category = "warning"
login_manager.session_protection = "strong"

@app.after_request
def set_security_headers(response):
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

def validate_filename(filename):
    if not filename or filename.strip() != filename:
        return False
    
    filename = secure_filename(filename)
    if '..' in filename or filename.startswith('.') or '/' in filename:
        return False
    
    return True

def validate_url(url):
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
        if len(password) < 8:
            raise ValueError("Senha deve ter pelo menos 8 caracteres")
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
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
    conteudo_html = db.Column(db.Text)  # HTML formatado
    resumo = db.Column(db.Text, nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    imagem = db.Column(db.String(200), default='default.jpg')
    link_materia = db.Column(db.String(500), nullable=False)
    data_publicacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_conteudo_html(self):
        if self.conteudo_html and self.conteudo_html.strip():
            return self.conteudo_html
        
        self.conteudo_html = formatar_conteudo_inteligente(self.conteudo)
        db.session.commit()
        return self.conteudo_html

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
    """Middleware de segurança para rotas administrativas - Adaptado para Render"""
    if request.path.startswith(ADMIN_URL_PREFIX):
        client_ip = request.remote_addr
        x_forwarded_for = request.headers.get('X-Forwarded-For')
        
        # No Render, pegar IP real dos headers
        if x_forwarded_for:
            client_ip = x_forwarded_for.split(',')[0].strip()
        
        # Converter ADMIN_IPS para lista
        allowed_ips = ADMIN_IPS.split(',') if isinstance(ADMIN_IPS, str) else ADMIN_IPS
        
        # Adicionar IPs internos do Render para permitir acesso
        render_ips = ['0.0.0.0', '127.0.0.1', '::1', 'localhost']
        allowed_ips.extend(render_ips)
        
        if client_ip not in allowed_ips:
            print(f"⚠️ Tentativa de acesso não autorizado de IP: {client_ip}")
            print(f"📡 IPs permitidos: {allowed_ips}")
            print(f"🌐 X-Forwarded-For: {x_forwarded_for}")
            abort(403, description="Acesso não autorizado. IP não permitido.")

# ========================================
# FUNÇÕES DE UPLOAD
# ========================================

def save_uploaded_file(file):
    if not file or file.filename == '':
        return None
    
    if not validate_filename(file.filename):
        return None
    
    file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    if file_ext not in ALLOWED_EXTENSIONS:
        return None
    
    try:
        filename = f"{uuid.uuid4().hex}.{file_ext}"
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
    configs = {}
    for config in Configuracao.query.all():
        configs[config.chave] = config.valor
    return render_template('public/index.html', configs=configs)

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
        configs = {}
        for config in Configuracao.query.all():
            configs[config.chave] = config.valor
        return render_template('public/planos.html', planos=planos_formatados, configs=configs)
    except Exception as e:
        print(f"Erro na rota /planos: {e}")
        return render_template('public/planos.html', planos=[], configs={})

@app.route('/blog')
def blog():
    try:
        posts = Post.query.filter_by(ativo=True).order_by(Post.data_publicacao.desc()).all()
        configs = {}
        for config in Configuracao.query.all():
            configs[config.chave] = config.valor
        return render_template('public/blog.html', configs=configs, posts=posts)
    except Exception as e:
        print(f"Erro na rota /blog: {e}")
        return render_template('public/blog.html', configs={}, posts=[])

@app.route('/velocimetro')
def velocimetro():
    configs = {}
    for config in Configuracao.query.all():
        configs[config.chave] = config.valor
    return render_template('public/velocimetro.html', configs=configs)

@app.route('/sobre')
def sobre():
    configs = {}
    for config in Configuracao.query.all():
        configs[config.chave] = config.valor
    return render_template('public/sobre.html', configs=configs)

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
                    if next_page:
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
            
            # Processar conteúdo com formatação inteligente
            conteudo_html = formatar_conteudo_inteligente(conteudo)
            
            novo_post = Post(
                titulo=titulo,
                conteudo=conteudo,
                conteudo_html=conteudo_html,
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
            post.conteudo_html = formatar_conteudo_inteligente(conteudo)
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
    
    configs = {}
    for config in Configuracao.query.all():
        configs[config.chave] = config.valor
    return render_template('admin/configuracoes.html', configs=configs)

# ========================================
# UTILITÁRIOS
# ========================================

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
                'conteudo': post.get_conteudo_html()
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
    return render_template('public/404.html'), 404

@app.errorhandler(403)
def acesso_negado(error):
    print(f"Acesso negado: {request.remote_addr} - {request.path}")
    return render_template('public/403.html'), 403

@app.errorhandler(500)
def erro_servidor(error):
    print(f"Erro interno do servidor: {error}")
    return render_template('public/500.html'), 500

# ========================================
# INICIALIZAÇÃO
# ========================================

def create_tables():
    with app.app_context():
        try:
            db.create_all()
            
            upload_path = app.config['UPLOAD_FOLDER']
            os.makedirs(upload_path, exist_ok=True)
            
            if AdminUser.query.filter_by(username=ADMIN_USERNAME).first() is None:
                admin_user = AdminUser(
                    username=ADMIN_USERNAME, 
                    email=ADMIN_EMAIL
                )
                admin_user.set_password(ADMIN_PASSWORD)
                db.session.add(admin_user)
                db.session.commit()
                print("Usuário administrativo criado com sucesso")
            
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
                    post.conteudo_html = formatar_conteudo_inteligente(post.conteudo)
                    db.session.add(post)
                
                print("Posts de exemplo adicionados com sucesso!")
            
            db.session.commit()
            print("Banco de dados inicializado com sucesso!")
            
        except Exception as e:
            print(f"Erro ao inicializar banco de dados: {e}")
            db.session.rollback()

if __name__ == '__main__':
    create_tables()
    debug_mode = os.environ.get('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
# ========================================
# INICIALIZAÇÃO PARA RENDER.COM
# ========================================

def create_database():
    """Função para criar banco de dados se não existir"""
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    
    # Pegar URL do banco de dados
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url:
        try:
            # Extrair informações da URL
            parsed_url = urlparse(database_url)
            
            # Conectar ao PostgreSQL server
            conn = psycopg2.connect(
                database='postgres',
                user=parsed_url.username,
                password=parsed_url.password,
                host=parsed_url.hostname,
                port=parsed_url.port
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cur = conn.cursor()
            
            # Criar banco de dados se não existir
            db_name = parsed_url.path[1:]  # Remove a barra inicial
            cur.execute(f"SELECT 1 FROM pg_database WHERE datname='{db_name}'")
            exists = cur.fetchone()
            
            if not exists:
                cur.execute(f'CREATE DATABASE {db_name}')
                print(f"✅ Banco de dados '{db_name}' criado")
            
            cur.close()
            conn.close()
        except Exception as e:
            print(f"⚠️ Não foi possível criar banco de dados: {e}")
            print("🔧 Usando banco existente ou configurado...")

if __name__ == '__main__':
    # Configurações para Render
    create_database()  # Tentar criar banco se não existir
    create_tables()
    
    # Usar porta do Render ou 10000 como fallback
    port = int(os.environ.get('PORT', 10000))
    
    debug_mode = os.environ.get('FLASK_ENV') != 'production'
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug_mode,
        threaded=True
    )    