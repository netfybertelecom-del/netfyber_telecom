#!/bin/bash
echo "🚀 Iniciando build no Render..."
echo "📦 Python version: $(python --version)"

# Instalar dependências
pip install --upgrade pip
pip install -r requirements.txt

# Criar pastas necessárias (apenas para fallback)
mkdir -p static/uploads/blog
mkdir -p static/images/blog

echo "✅ Build concluído com sucesso!"