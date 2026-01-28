#!/bin/bash
echo "🚀 Iniciando NetFyber Telecom no Render..."
echo "📦 Python: $(python --version)"
echo "🔧 Ambiente: $FLASK_ENV"
echo "🌐 Porta: $PORT"

# Criar diretórios necessários
mkdir -p static/uploads/blog
mkdir -p static/images/blog
mkdir -p static/images

# Instalar dependências específicas se necessário
pip install psycopg2-binary --no-cache-dir

# Executar a aplicação com Gunicorn
exec gunicorn app:app \
    --bind 0.0.0.0:$PORT \
    --workers=2 \
    --threads=4 \
    --timeout=120 \
    --access-logfile - \
    --error-logfile -