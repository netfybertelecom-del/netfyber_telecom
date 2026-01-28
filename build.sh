#!/bin/bash
echo "🚀 Iniciando build no Render..."
echo "📦 Python: $(python --version)"

# Instalar dependências
pip install --upgrade pip
pip install -r requirements.txt

# Tornar o start.sh executável
chmod +x start.sh

echo "✅ Build concluído!"