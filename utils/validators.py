import re
from urllib.parse import urlparse

def validate_email(email):
    """Validação simples de email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    """Validação de telefone brasileiro"""
    phone = re.sub(r'\D', '', phone)
    return len(phone) >= 10 and len(phone) <= 11

def validate_url(url):
    """Validação de URL"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

def validate_password(password):
    """Validação de senha forte"""
    if len(password) < 8:
        return False
    if not re.search(r'[A-Z]', password):
        return False
    if not re.search(r'[a-z]', password):
        return False
    if not re.search(r'\d', password):
        return False
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False
    return True