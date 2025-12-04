#!/bin/bash
# render-build.sh

echo "🚀 Iniciando build no Render..."
echo "📦 Python version: $(python --version)"
echo "📦 Pip version: $(pip --version)"

# Instalar dependências
pip install --upgrade pip
pip install -r requirements.txt

# Criar pastas necessárias
mkdir -p static/uploads/blog
mkdir -p static/images/blog

echo "✅ Build concluído!"