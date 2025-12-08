#!/bin/bash
echo "🚀 Iniciando build no Render..."
echo "📦 Python version: $(python --version)"
echo "🐍 Python path: $(which python)"

# Forçar Python 3.11 se estiver disponível
if command -v python3.11 &> /dev/null; then
    echo "🔄 Usando Python 3.11 explicitamente"
    PYTHON_CMD=python3.11
    PIP_CMD=pip3.11
else
    PYTHON_CMD=python
    PIP_CMD=pip
fi

# Instalar dependências
$PIP_CMD install --upgrade pip
$PIP_CMD install -r requirements.txt

# Verificar instalações críticas
echo "🔍 Verificando dependências críticas..."
$PYTHON_CMD -c "import flask; print(f'✅ Flask: {flask.__version__}')"
$PYTHON_CMD -c "try: import psycopg2; print('✅ psycopg2 instalado'); except: print('❌ psycopg2 não encontrado')"
$PYTHON_CMD -c "try: import psycopg; print('✅ psycopg instalado'); except: print('❌ psycopg não encontrado')"

# Criar pastas necessárias
mkdir -p static/uploads/blog
mkdir -p static/images/blog

# Configurar permissões
chmod -R 755 static/

echo "✅ Build concluído!"