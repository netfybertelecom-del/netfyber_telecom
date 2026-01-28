#!/bin/bash
echo "🚀 Iniciando NetFyber Telecom no Render..."
echo "📦 Python: $(python --version)"
echo "🔧 FLASK_ENV: $FLASK_ENV"
echo "📊 DATABASE_URL: ${DATABASE_URL:0:50}..."

# Criar diretórios necessários
mkdir -p static/uploads/blog
mkdir -p static/images/blog

# Iniciar o Gunicorn
exec gunicorn --bind 0.0.0.0:$PORT app:app --workers=2 --threads=4 --timeout=120