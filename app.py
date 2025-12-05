# -*- coding: utf-8 -*-
"""
NetFyber Telecom - Sistema Completo
Versão corrigida para hospedagem no Render
"""

import os
import sys
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import uuid
from sqlalchemy import text
from dotenv import load_dotenv

# ========================================
# CONFIGURAÇÃO INICIAL
# ========================================
load_dotenv()

# Verificar versão Python
if sys.version_info >= (3, 13):
    print(f"❌ ERRO: Python {sys.version_info.major}.{sys.version_info.minor} não suportado!")
    print("✅ Use Python 3.12.10")
    sys.exit(1)

app = Flask(__name__)

# ========================================
# CONFIGURAÇÕES DO APP
# ========================================
def get_database_url():
    """Corrige URL do banco de dados para Render"""
    db_url = os.environ.get('DATABASE_URL')
    
    if db_url:
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)
            print("🔄 URL convertida para postgresql://")
    else:
        db_url = 'sqlite:///netfyber.db'
        print("📁 Usando SQLite (desenvolvimento)")
    
    return db_url

# Configurações
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production-2025')
app.config['SQLALCHEMY_DATABASE_URI'] = get_database_url()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads/blog'
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 horas

# Configuração específica para Render
if 'RENDER' in os.environ:
    print("🚀 Ambiente Render detectado")
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_recycle': 300,
        'pool_pre_ping': True,
        'pool_size': 5,
        'max_overflow': 10,
    }

# Variáveis de admin
ADMIN_URL_PREFIX = os.environ.get('ADMIN_URL_PREFIX', '/gestao-exclusiva-netfyber')
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'netfyber_admin')
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@netfyber.com')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Admin@Netfyber2025!')

# ========================================
# BANCO DE DADOS
# ========================================
db = SQLAlchemy(app)

# ========================================
# MODELOS
# ========================================
class AdminUser(UserMixin, db.Model):
    __tablename__ = 'admin_users'
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
    imagem = db.Column(db.String(200), default='default.jpg')
    link_materia = db.Column(db.String(500), nullable=False)
    data_publicacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_data_formatada(self):
        return self.data_publicacao.strftime('%d/%m/%Y')

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
# FUNÇÕES AUXILIARES CORRIGIDAS
# ========================================
def get_configs():
    """Busca configurações do banco de dados com tratamento robusto de erro"""
    # Configurações padrão (definidas ANTES do try)
    default_configs = {
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
    
    try:
        # Testar conexão com o banco
        db.session.execute(text('SELECT 1'))
        
        configs = {}
        for config in Configuracao.query.all():
            configs[config.chave] = config.valor
        
        print(f"✅ Configurações carregadas: {len(configs)} itens")
        
        # Mesclar com configurações padrão se faltarem
        for key, value in default_configs.items():
            if key not in configs:
                configs[key] = value
        
        return configs
        
    except Exception as e:
        # Não imprimir o erro para não poluir os logs
        # Apenas retornar as configurações padrão
        return default_configs

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
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
# HANDLERS DE SESSÃO (NOVO)
# ========================================
@app.before_request
def before_request():
    """Garante que a sessão do banco está limpa antes de cada requisição"""
    try:
        # Fechar qualquer sessão antiga
        db.session.close()
    except:
        pass

@app.teardown_request
def teardown_request(exception=None):
    """Limpa a sessão após cada requisição"""
    if exception:
        db.session.rollback()
    else:
        try:
            db.session.commit()
        except:
            db.session.rollback()
    db.session.close()

# ========================================
# CONTEXT PROCESSOR
# ========================================
@app.context_processor
def inject_configs():
    return {'configs': get_configs()}

# ========================================
# ROTAS PÚBLICAS
# ========================================
@app.route('/')
def index():
    return render_template('public/index.html')

@app.route('/planos')
def planos():
    planos_data = Plano.query.filter_by(ativo=True).order_by(Plano.ordem_exibicao).all()
    return render_template('public/planos.html', planos=planos_data)

@app.route('/blog')
def blog():
    posts = Post.query.filter_by(ativo=True).order_by(Post.data_publicacao.desc()).all()
    return render_template('public/blog.html', posts=posts)

@app.route('/velocimetro')
def velocimetro():
    return render_template('public/velocimetro.html')

@app.route('/sobre')
def sobre():
    return render_template('public/sobre.html')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico')

# ========================================
# ROTAS DE ADMIN
# ========================================
@app.route(f'{ADMIN_URL_PREFIX}/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_planos'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            user = AdminUser.query.filter_by(username=username).first()
            if not user:
                user = AdminUser(username=username, email=ADMIN_EMAIL, is_active=True)
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
            
            login_user(user)
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('admin_planos'))
        else:
            flash('Credenciais inválidas', 'error')
    
    return render_template('auth/login.html')

@app.route(f'{ADMIN_URL_PREFIX}/logout')
@login_required
def admin_logout():
    logout_user()
    flash('Logout realizado com sucesso', 'info')
    return redirect(url_for('admin_login'))

@app.route(f'{ADMIN_URL_PREFIX}/planos')
@login_required
def admin_planos():
    planos = Plano.query.order_by(Plano.ordem_exibicao).all()
    return render_template('admin/planos.html', planos=planos)

@app.route(f'{ADMIN_URL_PREFIX}/planos/novo', methods=['GET', 'POST'])
@login_required
def adicionar_plano():
    if request.method == 'POST':
        try:
            plano = Plano(
                nome=request.form.get('nome', '').strip(),
                preco=request.form.get('preco', '').strip(),
                velocidade=request.form.get('velocidade', '').strip(),
                features=request.form.get('features', '').strip(),
                recomendado='recomendado' in request.form,
                ativo=True
            )
            db.session.add(plano)
            db.session.commit()
            flash('Plano criado com sucesso!', 'success')
            return redirect(url_for('admin_planos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {str(e)}', 'error')
    
    return render_template('admin/plano_form.html', plano=None)

@app.route(f'{ADMIN_URL_PREFIX}/planos/editar/<int:plano_id>', methods=['GET', 'POST'])
@login_required
def editar_plano(plano_id):
    plano = Plano.query.get_or_404(plano_id)
    
    if request.method == 'POST':
        try:
            plano.nome = request.form.get('nome', '').strip()
            plano.preco = request.form.get('preco', '').strip()
            plano.velocidade = request.form.get('velocidade', '').strip()
            plano.features = request.form.get('features', '').strip()
            plano.recomendado = 'recomendado' in request.form
            db.session.commit()
            flash('Plano atualizado com sucesso!', 'success')
            return redirect(url_for('admin_planos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {str(e)}', 'error')
    
    return render_template('admin/plano_form.html', plano=plano)

@app.route(f'{ADMIN_URL_PREFIX}/planos/excluir/<int:plano_id>', methods=['POST'])
@login_required
def excluir_plano(plano_id):
    try:
        plano = Plano.query.get_or_404(plano_id)
        db.session.delete(plano)
        db.session.commit()
        flash('Plano excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {str(e)}', 'error')
    
    return redirect(url_for('admin_planos'))

@app.route(f'{ADMIN_URL_PREFIX}/blog')
@login_required
def admin_blog():
    posts = Post.query.order_by(Post.data_publicacao.desc()).all()
    return render_template('admin/blog.html', posts=posts)

@app.route(f'{ADMIN_URL_PREFIX}/blog/novo', methods=['GET', 'POST'])
@login_required
def adicionar_post():
    if request.method == 'POST':
        try:
            conteudo = request.form.get('conteudo', '').strip()
            post = Post(
                titulo=request.form.get('titulo', '').strip(),
                conteudo=conteudo,
                resumo=conteudo[:150] + '...' if len(conteudo) > 150 else conteudo,
                categoria=request.form.get('categoria', '').strip(),
                link_materia=request.form.get('link_materia', '').strip(),
                ativo=True
            )
            
            imagem = request.files.get('imagem')
            if imagem and imagem.filename:
                filename = save_uploaded_file(imagem)
                if filename:
                    post.imagem = filename
            
            db.session.add(post)
            db.session.commit()
            flash('Post criado com sucesso!', 'success')
            return redirect(url_for('admin_blog'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {str(e)}', 'error')
    
    return render_template('admin/post_form.html', post=None)

@app.route(f'{ADMIN_URL_PREFIX}/blog/editar/<int:post_id>', methods=['GET', 'POST'])
@login_required
def editar_post(post_id):
    post = Post.query.get_or_404(post_id)
    
    if request.method == 'POST':
        try:
            post.titulo = request.form.get('titulo', '').strip()
            post.conteudo = request.form.get('conteudo', '').strip()
            post.resumo = post.conteudo[:150] + '...' if len(post.conteudo) > 150 else post.conteudo
            post.categoria = request.form.get('categoria', '').strip()
            post.link_materia = request.form.get('link_materia', '').strip()
            post.ativo = 'ativo' in request.form
            
            imagem = request.files.get('imagem')
            if imagem and imagem.filename:
                filename = save_uploaded_file(imagem)
                if filename:
                    post.imagem = filename
            
            db.session.commit()
            flash('Post atualizado com sucesso!', 'success')
            return redirect(url_for('admin_blog'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {str(e)}', 'error')
    
    return render_template('admin/post_form.html', post=post)

@app.route(f'{ADMIN_URL_PREFIX}/blog/excluir/<int:post_id>', methods=['POST'])
@login_required
def excluir_post(post_id):
    try:
        post = Post.query.get_or_404(post_id)
        db.session.delete(post)
        db.session.commit()
        flash('Post excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {str(e)}', 'error')
    
    return redirect(url_for('admin_blog'))

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
            flash('Configurações salvas com sucesso!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {str(e)}', 'error')
    
    configs = {c.chave: c.valor for c in Configuracao.query.all()}
    return render_template('admin/configuracoes.html', configs=configs)

# ========================================
# UTILIDADES
# ========================================
@app.route('/health')
def health_check():
    try:
        db.session.execute(text('SELECT 1'))
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

# ========================================
# HANDLERS DE ERRO (CORRIGIDOS)
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
# INICIALIZAÇÃO ROBUSTA DO BANCO
# ========================================
def init_database():
    """Inicializa o banco de dados com tratamento completo de erros"""
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            print(f"🔧 Tentativa {retry_count + 1}/{max_retries}: Inicializando banco de dados...")
            
            # Verificar se já existe conexão ativa
            try:
                db.session.execute(text('SELECT 1'))
            except:
                print("🔄 Reconectando ao banco...")
            
            # Criar tabelas se não existirem (com IF NOT EXISTS implícito)
            db.create_all()
            print("✅ Tabelas verificadas/criadas")
            
            # Criar usuário admin se não existir
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
                print(f"✅ Admin criado: {admin_username}")
            
            # Configurações padrão
            configs_padrao = [
                ('telefone_contato', '(63) 8494-1778', 'Telefone de contato'),
                ('email_contato', 'contato@netfyber.com', 'Email de contato'),
                ('endereco', 'AV. Tocantins – 934, Centro – Sítio Novo – TO<br>Axixá TO / Juverlândia / São Pedro / Folha Seca / Morada Nova / Santa Luzia / Boa Esperança', 'Endereço completo'),
                ('horario_segunda_sexta', '08h às 18h', 'Horário de segunda a sexta'),
                ('horario_sabado', '08h às 13h', 'Horário de sábado'),
                ('whatsapp_numero', '556384941778', 'Número do WhatsApp para contato'),
                ('instagram_url', 'https://www.instagram.com/netfybertelecom', 'URL do Instagram'),
                ('hero_imagem', 'images/familia.png', 'Imagem da seção hero'),
                ('hero_titulo', 'Internet de Alta Velocidade', 'Título principal do hero'),
                ('hero_subtitulo', 'Conecte sua família ao futuro com a NetFyber Telecom', 'Subtítulo do hero')
            ]
            
            for chave, valor, descricao in configs_padrao:
                config = Configuracao.query.filter_by(chave=chave).first()
                if not config:
                    config = Configuracao(
                        chave=chave,
                        valor=valor,
                        descricao=descricao,
                        created_at=datetime.utcnow()
                    )
                    db.session.add(config)
                    print(f"⚙️  Configuração padrão adicionada: {chave}")
            
            # Planos de exemplo (apenas se não houver nenhum plano)
            if Plano.query.count() == 0:
                print("📡 Criando planos de exemplo...")
                
                planos_exemplo = [
                    {
                        'nome': '100 MEGA',
                        'preco': '69,90',
                        'velocidade': '100 Mbps',
                        'features': 'Wi-Fi Grátis\nInstalação Grátis\nSuporte 24h\nFibra Óptica',
                        'recomendado': False,
                        'ordem_exibicao': 1,
                        'ativo': True
                    },
                    {
                        'nome': '200 MEGA',
                        'preco': '79,90',
                        'velocidade': '200 Mbps',
                        'features': 'Wi-Fi Grátis\nInstalação Grátis\nSuporte 24h\nFibra Óptica\nModem Incluso',
                        'recomendado': True,
                        'ordem_exibicao': 2,
                        'ativo': True
                    },
                    {
                        'nome': '400 MEGA',
                        'preco': '89,90',
                        'velocidade': '400 Mbps',
                        'features': 'Wi-Fi Grátis\nInstalação Grátis\nSuporte 24h\nFibra Óptica\nModem Incluso\nAntivírus',
                        'recomendado': False,
                        'ordem_exibicao': 3,
                        'ativo': True
                    }
                ]
                
                for plano_data in planos_exemplo:
                    plano = Plano(
                        nome=plano_data['nome'],
                        preco=plano_data['preco'],
                        velocidade=plano_data['velocidade'],
                        features=plano_data['features'],
                        recomendado=plano_data['recomendado'],
                        ordem_exibicao=plano_data['ordem_exibicao'],
                        ativo=plano_data['ativo'],
                        created_at=datetime.utcnow()
                    )
                    db.session.add(plano)
            
            # Commit final
            db.session.commit()
            print("🎉 Banco inicializado com sucesso!")
            return True
            
        except Exception as e:
            retry_count += 1
            print(f"❌ Erro na tentativa {retry_count}: {e}")
            db.session.rollback()
            
            if retry_count < max_retries:
                print(f"⏳ Aguardando 2 segundos antes de tentar novamente...")
                import time
                time.sleep(2)
            else:
                print("💥 Todas as tentativas falharam. Verifique a conexão com o banco.")
                return False

# ========================================
# INICIALIZAÇÃO DO BANCO AO INICIAR O APP
# ========================================
with app.app_context():
    print("🚀 Inicializando banco de dados...")
    try:
        init_database()
    except Exception as e:
        print(f"⚠️  Erro na inicialização do banco: {e}")

# ========================================
# MAIN
# ========================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    print(f"🌐 Porta: {port}")
    print(f"🔗 Painel Admin: {ADMIN_URL_PREFIX}/login")
    print(f"👤 Usuário admin: {ADMIN_USERNAME}")
    print(f"🔧 Modo debug: {debug}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug,
        threaded=True
    )