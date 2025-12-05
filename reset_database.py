#!/usr/bin/env python3
"""
Script para resetar o banco de dados do NetFyber Telecom
Executar: python reset_database.py [--force]
"""

import os
import sys
from datetime import datetime

# Adiciona o diretório atual ao path para importar o app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db, AdminUser, Plano, Configuracao, Post
from werkzeug.security import generate_password_hash

def reset_database():
    """Reset completo do banco de dados com dados de exemplo"""
    with app.app_context():
        try:
            print("="*60)
            print("🔄 RESET COMPLETO DO BANCO DE DADOS - NETFYBER")
            print("="*60)
            
            # Confirmação de segurança
            if len(sys.argv) > 1 and sys.argv[1] == "--force":
                print("⚠️  Modo forçado ativado...")
            else:
                confirm = input("\n⚠️  ATENÇÃO: Isso apagará TODOS os dados existentes. Continuar? (s/N): ")
                if confirm.lower() != 's':
                    print("❌ Operação cancelada pelo usuário.")
                    return
            
            print("\n📦 Iniciando processo de reset...")
            
            # 1. Drop todas as tabelas
            print("🗑️  Removendo tabelas existentes...")
            db.drop_all()
            
            # 2. Criar tabelas com estrutura atualizada
            print("🏗️  Criando novas tabelas...")
            db.create_all()
            
            # 3. Criar usuário administrativo
            print("👤 Criando usuário administrativo...")
            
            admin_data = {
                'username': os.environ.get('ADMIN_USERNAME', 'netfyber_admin'),
                'email': os.environ.get('ADMIN_EMAIL', 'admin@netfyber.com'),
                'password': os.environ.get('ADMIN_PASSWORD', 'Admin@Netfyber2025!')
            }
            
            # Verificar se a senha atende aos requisitos mínimos
            if len(admin_data['password']) < 8:
                print("⚠️  Aviso: Senha muito curta. Usando senha padrão segura...")
                admin_data['password'] = 'Ny7@F8b#2qP9!vM0xW3c$K5'
            
            admin_user = AdminUser(
                username=admin_data['username'],
                email=admin_data['email'],
                is_active=True
            )
            admin_user.password_hash = generate_password_hash(admin_data['password'])
            admin_user.created_at = datetime.utcnow()
            
            db.session.add(admin_user)
            db.session.flush()
            
            # 4. Configurações padrão do site
            print("⚙️  Configurando site...")
            
            configs_padrao = [
                ('telefone_contato', '(63) 8494-1778', 'Telefone de contato'),
                ('email_contato', 'contato@netfyber.com', 'Email de contato'),
                ('endereco', 'AV. Tocantins – 934, Centro – Sítio Novo – TO', 'Endereço completo'),
                ('horario_segunda_sexta', '08h às 18h', 'Horário de segunda a sexta'),
                ('horario_sabado', '08h às 13h', 'Horário de sábado'),
                ('whatsapp_numero', '556384941778', 'Número do WhatsApp para contato'),
                ('instagram_url', 'https://www.instagram.com/netfybertelecom', 'URL do Instagram'),
                ('facebook_url', '#', 'URL do Facebook'),
                ('hero_imagem', 'images/familia.png', 'Imagem da seção hero'),
                ('hero_titulo', 'Internet de Alta Velocidade', 'Título principal do hero'),
                ('hero_subtitulo', 'Conecte sua família ao futuro com a NetFyber Telecom', 'Subtítulo do hero')
            ]
            
            for chave, valor, descricao in configs_padrao:
                config = Configuracao(
                    chave=chave,
                    valor=valor,
                    descricao=descricao,
                    created_at=datetime.utcnow()
                )
                db.session.add(config)
            
            # 5. Planos de exemplo
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
            
            # 6. Posts de blog de exemplo
            print("📝 Criando posts do blog...")
            
            posts_exemplo = [
                {
                    'titulo': 'NetFyber inaugura nova infraestrutura de fibra óptica',
                    'conteudo': 'A NetFyber Telecom anunciou hoje a expansão de sua rede de fibra óptica para mais 5 bairros na região. A nova infraestrutura permitirá velocidades de até 1Gbps para residências e empresas.\n\nCom investimento de R$ 2 milhões, a empresa planeja atingir 10.000 novas casas até o final do ano. "Estamos comprometidos em levar internet de alta qualidade para toda a região", afirmou o CEO João Silva.',
                    'resumo': 'NetFyber expande rede de fibra óptica com investimento de R$ 2 milhões para atingir 10.000 novas residências.',
                    'categoria': 'noticias',
                    'imagem': 'default.jpg',
                    'link_materia': 'https://exemplo.com/noticia1',
                    'data_publicacao': datetime(2025, 1, 15)
                },
                {
                    'titulo': 'Como escolher o melhor plano de internet para sua casa',
                    'conteudo': 'Com tantas opções disponíveis, escolher o plano de internet ideal pode ser desafiador. Neste artigo, explicamos os fatores a considerar:\n\n1. Número de dispositivos conectados\n2. Uso principal (trabalho, estudo, entretenimento)\n3. Velocidade necessária para streaming em 4K\n4. Orçamento disponível\n\nPara uma família de 4 pessoas com uso intenso de streaming, recomendamos planos a partir de 200Mbps.',
                    'resumo': 'Guia completo para ajudar você a escolher o plano de internet ideal baseado no seu uso e necessidades.',
                    'categoria': 'dicas',
                    'imagem': 'default.jpg',
                    'link_materia': 'https://exemplo.com/noticia2',
                    'data_publicacao': datetime(2025, 2, 10)
                },
                {
                    'titulo': 'A importância da estabilidade da conexão para home office',
                    'conteudo': 'Com o aumento do trabalho remoto, uma conexão estável tornou-se essencial. Problemas de conexão podem resultar em:\n\n- Reuniões interrompidas\n- Perda de dados importantes\n- Atrasos na entrega de projetos\n- Estresse e redução de produtividade\n\nA NetFyber oferece conexões com 99,9% de estabilidade, garantindo que seu trabalho não seja interrompido.',
                    'resumo': 'Entenda por que uma conexão estável é crucial para o trabalho remoto e como a NetFyber pode ajudar.',
                    'categoria': 'tecnologia',
                    'imagem': 'default.jpg',
                    'link_materia': 'https://exemplo.com/noticia3',
                    'data_publicacao': datetime(2025, 3, 5)
                }
            ]
            
            for post_data in posts_exemplo:
                post = Post(
                    titulo=post_data['titulo'],
                    conteudo=post_data['conteudo'],
                    resumo=post_data['resumo'],
                    categoria=post_data['categoria'],
                    imagem=post_data['imagem'],
                    link_materia=post_data['link_materia'],
                    data_publicacao=post_data['data_publicacao'],
                    ativo=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.session.add(post)
            
            # Commit final
            db.session.commit()
            
            print("\n" + "="*60)
            print("✅ RESET CONCLUÍDO COM SUCESSO!")
            print("="*60)
            
            # Resumo
            print("\n📊 RESUMO DA CRIAÇÃO:")
            print(f"   👤 Usuário administrativo: 1")
            print(f"   ⚙️  Configurações do site: {len(configs_padrao)}")
            print(f"   📡 Planos de internet: {len(planos_exemplo)}")
            print(f"   📝 Posts do blog: {len(posts_exemplo)}")
            
            print("\n👤 DETALHES DO ADMINISTRADOR:")
            print(f"   📧 Usuário: {admin_data['username']}")
            print(f"   📨 Email: {admin_data['email']}")
            print(f"   🔑 Senha: {admin_data['password']}")
            
            admin_url = os.environ.get('ADMIN_URL_PREFIX', '/gestao-exclusiva-netfyber')
            print(f"\n🌐 URL do Painel: {admin_url}/login")
            
            print("\n💡 PRÓXIMOS PASSOS:")
            print("   1. Inicie o servidor: python app.py")
            print("   2. Acesse o painel administrativo")
            print("   3. Verifique todas as funcionalidades")
            print("="*60)
            
            return True
            
        except Exception as e:
            print(f"\n❌ ERRO DURANTE O RESET: {e}")
            import traceback
            traceback.print_exc()
            print("\n🔧 Solução de problemas:")
            print("   1. Verifique se o banco de dados está acessível")
            print("   2. Confirme as credenciais do banco no .env")
            print("   3. Tente executar com: python reset_database.py --force")
            db.session.rollback()
            return False

if __name__ == '__main__':
    print("🚀 NETFYBER - SISTEMA DE RESET DE BANCO DE DADOS")
    print("📅 Versão: 2.0 | Data: Dezembro 2025")
    print()
    
    reset_database()