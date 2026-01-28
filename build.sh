#!/bin/bash
echo "🚀 Iniciando build no Render..."
echo "📦 Python version: $(python --version)"

# Instalar dependências
pip install --upgrade pip
pip install -r requirements.txt

# Criar pastas necessárias
mkdir -p static/uploads/blog
mkdir -p static/images/blog

# Configurar permissões
chmod -R 755 static/

echo "✅ Build concluído!"