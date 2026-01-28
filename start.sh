#!/bin/bash
echo "🚀 Iniciando NetFyber Telecom..."
echo "📦 Python: $(python --version)"
echo "🔧 Ambiente: $FLASK_ENV"

# Criar diretórios necessários
mkdir -p static/uploads/blog
mkdir -p static/images/blog

# Inicializar banco de dados
python -c "
from app import app, init_database
with app.app_context():
    init_database()
    print('✅ Banco inicializado')
"

# Iniciar Gunicorn
exec gunicorn --bind 0.0.0.0:$PORT app:app \
    --workers=2 \
    --threads=4 \
    --timeout=120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info