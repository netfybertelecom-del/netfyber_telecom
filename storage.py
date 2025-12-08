import os
import uuid
from werkzeug.utils import secure_filename
from flask import current_app

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    """Verifica se o arquivo tem uma extensão permitida"""
    if not filename:
        return False
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_file_local(file):
    """Salva o arquivo localmente no sistema de arquivos"""
    if not allowed_file(file.filename):
        return None
    
    try:
        filename = f"{uuid.uuid4().hex}.{file.filename.rsplit('.', 1)[1].lower()}"
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            return {
                'filename': filename,
                'storage_type': 'local',
                'url': f"/static/uploads/blog/{filename}"
            }
    except Exception as e:
        print(f"Erro ao salvar arquivo localmente: {e}")
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
    
    return None

def save_file_s3(file):
    """Salva o arquivo no Cloudflare R2 (S3 compatível)"""
    if not allowed_file(file.filename):
        return None
    
    try:
        import boto3
        from botocore.exceptions import ClientError
        
        s3_enabled = current_app.config.get('S3_ENABLED', False)
        if not s3_enabled:
            return None
        
        # Configurar cliente S3 para Cloudflare R2
        s3_client = boto3.client(
            's3',
            endpoint_url=current_app.config.get('S3_ENDPOINT_URL'),
            region_name=current_app.config.get('S3_REGION', 'auto'),
            aws_access_key_id=current_app.config.get('S3_ACCESS_KEY_ID'),
            aws_secret_access_key=current_app.config.get('S3_SECRET_ACCESS_KEY')
        )
        
        filename = f"{uuid.uuid4().hex}.{file.filename.rsplit('.', 1)[1].lower()}"
        bucket_name = current_app.config.get('S3_BUCKET')
        
        # Fazer upload para Cloudflare R2
        s3_client.upload_fileobj(
            file,
            bucket_name,
            filename,
            ExtraArgs={
                'ACL': 'public-read',
                'ContentType': file.content_type or 'image/jpeg'
            }
        )
        
        # Cloudflare R2 usa URL diferente do S3 padrão
        # Formato: https://account-id.r2.cloudflarestorage.com/bucket-name/filename
        endpoint = current_app.config['S3_ENDPOINT_URL'].rstrip('/')
        url = f"{endpoint}/{bucket_name}/{filename}"
        
        return {
            'filename': filename,
            'storage_type': 's3',
            'url': url
        }
        
    except Exception as e:
        print(f"Erro ao salvar arquivo no Cloudflare R2: {e}")
        return None

def save_file(file):
    """Salva o arquivo usando o método apropriado (local ou Cloudflare R2)"""
    s3_enabled = current_app.config.get('S3_ENABLED', False)
    
    # Tentar Cloudflare R2 primeiro se estiver habilitado
    if s3_enabled:
        result = save_file_s3(file)
        if result:
            return result
    
    # Fallback para armazenamento local
    return save_file_local(file)

def delete_file_local(filename):
    """Exclui arquivo local"""
    try:
        upload_folder = current_app.config['UPLOAD_FOLDER']
        file_path = os.path.join(upload_folder, filename)
        
        if not os.path.abspath(file_path).startswith(os.path.abspath(upload_folder)):
            return False
            
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
    except Exception:
        return False
    
    return False

def delete_file_s3(filename):
    """Exclui arquivo do Cloudflare R2"""
    try:
        import boto3
        
        s3_client = boto3.client(
            's3',
            endpoint_url=current_app.config.get('S3_ENDPOINT_URL'),
            region_name=current_app.config.get('S3_REGION', 'auto'),
            aws_access_key_id=current_app.config.get('S3_ACCESS_KEY_ID'),
            aws_secret_access_key=current_app.config.get('S3_SECRET_ACCESS_KEY')
        )
        
        bucket_name = current_app.config.get('S3_BUCKET')
        s3_client.delete_object(Bucket=bucket_name, Key=filename)
        return True
        
    except Exception:
        return False