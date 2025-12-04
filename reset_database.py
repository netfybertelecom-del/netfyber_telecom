from app import app, db, AdminUser, Plano, Configuracao, Post
from werkzeug.security import generate_password_hash
from datetime import datetime
import os
import sys

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
                ('endereco', 'AV. Tocantins – 934, Centro – Sítio Novo – TO<br>Axixá TO / Juverlândia / São Pedro / Folha Seca / Morada Nova / Santa Luzia / Boa Esperança', 'Endereço completo'),
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
                    'ordem_exibicao': 1
                },
                {
                    'nome': '200 MEGA',
                    'preco': '79,90',
                    'velocidade': '200 Mbps',
                    'features': 'Wi-Fi Grátis\nInstalação Grátis\nSuporte 24h\nFibra Óptica\nModem Incluso',
                    'recomendado': True,
                    'ordem_exibicao': 2
                },
                {
                    'nome': '400 MEGA',
                    'preco': '89,90',
                    'velocidade': '400 Mbps',
                    'features': 'Wi-Fi Grátis\nInstalação Grátis\nSuporte 24h\nFibra Óptica\nModem Incluso\nAntivírus',
                    'recomendado': False,
                    'ordem_exibicao': 3
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
                    ativo=True,
                    created_at=datetime.utcnow()
                )
                db.session.add(plano)
            
            # 6. Posts de blog de exemplo com formatação inteligente
            print("📝 Criando posts do blog...")
            
            # Importar a função de formatação do app
            from app import formatar_conteudo_inteligente
            
            posts_exemplo = [
                {
                    'titulo': 'IA generativa cresce fortemente, mas requer estratégia bem pensada',
                    'conteudo': 'De acordo com executivos do Itaú e do Banco do Brasil, a inteligência artificial generativa tem grande potencial disruptivo, mas exige investimento significativo e planejamento estratégico — "não basta usar por usar", segundo Marisa Reghini, do BB.\n\n**Muitos bancos preparam uso de "agentes de IA" para automatizar tarefas complexas.**\n<a href="https://www.ibm.com/br-pt/news" target="_blank" rel="noopener noreferrer">IBM Brasil Newsroom</a>\n\n**Apesar do entusiasmo, existe cautela sobre os custos e riscos da adoção.**\n<a href="https://veja.abril.com.br" target="_blank" rel="noopener noreferrer">VEJA</a>',
                    'resumo': 'IA generativa cresce fortemente, mas requer estratégia bem pensada. De acordo com executivos do Itaú e do Banco do Brasil...',
                    'categoria': 'tecnologia',
                    'imagem': 'default.jpg',
                    'link_materia': 'https://www.valor.com.br/tecnologia/noticia/ia-generativa-cresce-fortemente-mas-requer-estrategia',
                    'data_publicacao': datetime(2025, 11, 1)
                },
                {
                    'titulo': 'Investimentos em IA no Brasil devem ultrapassar US$ 2,4 bilhões em 2025',
                    'conteudo': 'Um estudo de projeção aponta que os gastos em IA (infraestrutura, software e serviços) devem alcançar cerca de US$ 2,4 bilhões ainda em 2025. Esse crescimento reflete a prioridade cada vez maior que as empresas brasileiras dão à IA generativa e outras tecnologias associadas.\n<a href="https://www.ianews.com.br" target="_blank" rel="noopener noreferrer">FelipeCFerreira IANews</a>\n\n**A IA não está mais apenas em pilotos: muitas empresas já planejam escalar para usos mais estratégicos.**\n<a href="https://www.xpi.com.br" target="_blank" rel="noopener noreferrer">XP Investimentos</a>\n\n**Parte desse investimento é direcionada a nuvem híbrida e open-source, segundo dados da NTT Data.**\n<a href="https://www.nttdata.com" target="_blank" rel="noopener noreferrer">IT Forum</a>',
                    'resumo': 'Investimentos em IA no Brasil devem ultrapassar US$ 2,4 bilhões em 2025. Um estudo de projeção aponta que os gastos em IA...',
                    'categoria': 'tecnologia',
                    'imagem': 'default.jpg',
                    'link_materia': 'https://www.ianews.com.br/investimentos-ia-brasil-2025',
                    'data_publicacao': datetime(2025, 8, 5)
                },
                {
                    'titulo': 'YouTube fecha acordo histórico para transmitir 38 jogos do Brasileirão (2025–2027)',
                    'conteudo': 'Segundo o jornalista Daniel Castro, o Google comprou os direitos para transmitir 38 jogos por ano do Brasileirão para a plataforma YouTube entre 2025 e 2027, em parceria com a CazéTV.\n<a href="https://www.noticiasdatv.com.br" target="_blank" rel="noopener noreferrer">Notícias da TV</a>\n\n**Os jogos serão os mesmos exibidos pela Record.**\n<a href="https://www.noticiasdatv.com.br" target="_blank" rel="noopener noreferrer">Notícias da TV</a>\n\n**Isso marca uma estratégia agressiva do Google para entrar no mercado de futebol no Brasil.**\n<a href="https://www.noticiasdatv.com.br" target="_blank" rel="noopener noreferrer">Notícias da TV</a>',
                    'resumo': 'YouTube fecha acordo histórico para transmitir 38 jogos do Brasileirão entre 2025 e 2027, em parceria com a CazéTV...',
                    'categoria': 'noticias',
                    'imagem': 'default.jpg',
                    'link_materia': 'https://www.noticiasdatv.com.br/youtube-brasileirao-2025',
                    'data_publicacao': datetime(2024, 10, 10)
                }
            ]
            
            for post_data in posts_exemplo:
                post = Post(
                    titulo=post_data['titulo'],
                    conteudo=post_data['conteudo'],
                    conteudo_html=formatar_conteudo_inteligente(post_data['conteudo']),
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
            print(f"   ⚙️ Configurações do site: {len(configs_padrao)}")
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
            print("\n🔧 Solução de problemas:")
            print("   1. Verifique se o PostgreSQL está rodando")
            print("   2. Confirme as credenciais do banco no .env")
            print("   3. Tente executar com: python reset_database.py --force")
            db.session.rollback()
            return False

if __name__ == '__main__':
    print("🚀 NETFYBER - SISTEMA DE RESET DE BANCO DE DADOS")
    print("📅 Versão: 2.0 | Data: Dezembro 2025")
    print()
    
    reset_database()