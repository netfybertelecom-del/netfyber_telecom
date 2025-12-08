#!/bin/bash
echo "🚀 Iniciando build no Render..."
echo "📦 Python version: $(python --version)"

# Instalar dependências
pip install --upgrade pip
pip install -r requirements.txt

# Criar pastas necessárias
mkdir -p static/uploads/blog
mkdir -p static/images/blog

# Criar arquivo .env com variáveis mínimas
if [ ! -f .env ]; then
    echo "SECRET_KEY=$(openssl rand -hex 32)" >> .env
    echo "FLASK_ENV=production" >> .env
fi

echo "✅ Build concluído!"