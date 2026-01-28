#!/bin/bash
echo "🚀 Iniciando NetFyber Telecom..."
echo "📦 Python: $(python --version)"

# Criar diretórios necessários
mkdir -p static/uploads/blog
mkdir -p static/images/blog

# Iniciar Gunicorn
exec gunicorn app:app \
    --bind 0.0.0.0:$PORT \
    --workers=2 \
    --threads=4 \
    --timeout=120