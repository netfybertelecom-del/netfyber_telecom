# reset_database.py
import os
import sys
from app import app, db
from app import AdminUser, Plano, Configuracao, Post
from werkzeug.security import generate_password_hash
from datetime import datetime

def reset_database():
    print("🚀 Iniciando reset do banco de dados...")
    
    with app.app_context():
        try:
            # Remover todas as tabelas
            print("📦 Removendo tabelas antigas...")
            db.drop_all()
            
            # Criar todas as tabelas
            print("🔄 Criando novas tabelas...")
            db.create_all()
            
            # Criar usuário admin padrão
            print("👤 Criando usuário admin...")
            admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
            admin_password = os.environ.get('ADMIN_PASSWORD', 'Teste123!')
            admin_email = os.environ.get('ADMIN_EMAIL', 'admin@netfyber.com')
            
            hashed_password = generate_password_hash(admin_password)
            admin = AdminUser(
                username=admin_username,
                email=admin_email,
                password_hash=hashed_password,
                is_active=True
            )
            db.session.add(admin)
            
            # Criar configurações padrão
            print("⚙️ Criando configurações padrão...")
            configs = [
                Configuracao(chave='telefone_contato', valor='(63) 8494-1778'),
                Configuracao(chave='email_contato', valor='contato@netfyber.com'),
                Configuracao(chave='endereco', valor='AV. Tocantins – 934, Centro – Sítio Novo – TO<br>Axixá TO / Juverlândia / São Pedro / Folha Seca / Morada Nova / Santa Luzia / Boa Esperança'),
                Configuracao(chave='horario_segunda_sexta', valor='08h às 18h'),
                Configuracao(chave='horario_sabado', valor='08h às 13h'),
                Configuracao(chave='whatsapp_numero', valor='556384941778'),
                Configuracao(chave='instagram_url', valor='https://www.instagram.com/netfybertelecom'),
                Configuracao(chave='hero_imagem', valor='images/familia.png'),
                Configuracao(chave='hero_titulo', valor='Internet de Alta Velocidade'),
                Configuracao(chave='hero_subtitulo', valor='Conecte sua família ao futuro com a NetFyber Telecom'),
            ]
            
            for config in configs:
                db.session.add(config)
            
            # Criar planos de exemplo
            print("📊 Criando planos de exemplo...")
            planos = [
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
            
            for plano in planos:
                db.session.add(plano)
            
            # Criar posts de exemplo
            print("📝 Criando posts de exemplo...")
            posts = [
                Post(
                    titulo='A importância da internet de alta velocidade',
                    conteudo='**A internet de alta velocidade** é essencial para o trabalho e estudo. Com a fibra óptica, você tem mais estabilidade e velocidade.\n\nAqui na NetFyber, oferecemos os melhores planos para sua família.',
                    resumo='A internet de alta velocidade é essencial para o trabalho e estudo...',
                    categoria='tecnologia',
                    imagem='default.jpg',
                    link_materia='https://exemplo.com/materia',
                    data_publicacao=datetime.utcnow(),
                    ativo=True
                ),
                Post(
                    titulo='NetFyber expande para novas regiões',
                    conteudo='Estamos felizes em anunciar a expansão da nossa rede para novas regiões. Agora mais pessoas podem ter acesso à internet de qualidade.\n\nConfira nossos planos e venha para a NetFyber!',
                    resumo='Estamos felizes em anunciar a expansão da nossa rede para novas regiões...',
                    categoria='noticias',
                    imagem='default.jpg',
                    link_materia='https://exemplo.com/noticia',
                    data_publicacao=datetime.utcnow(),
                    ativo=True
                ),
            ]
            
            for post in posts:
                db.session.add(post)
            
            # Salvar tudo
            db.session.commit()
            print("✅ Banco de dados resetado com sucesso!")
            print(f"📋 Credenciais de acesso:")
            print(f"   Usuário: {admin_username}")
            print(f"   Senha: {admin_password}")
            print(f"   Email: {admin_email}")
            print(f"🔗 Acesse: /gestao-exclusiva-netfyber/login")
            
        except Exception as e:
            print(f"❌ Erro ao resetar banco: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()

if __name__ == '__main__':
    reset_database()