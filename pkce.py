import os
import base64
import hashlib
import secrets
import string

def generate_code_verifier(length=128):
    """生成 PKCE code_verifier"""
    # 根据 RFC 7636 规范，code_verifier 应该是 43-128 字符长
    # 使用更简单但符合规范的方法
    
    # 确保长度在 43-128 之间
    if length < 43:
        length = 43
    elif length > 128:
        length = 128
    
    # 使用 secrets.token_urlsafe 生成符合规范的 code_verifier
    # token_urlsafe 生成 base64 URL 安全字符串，只包含 A-Z, a-z, 0-9, '-', '_'
    # 可能需要调整长度以获得所需字符数
    code_verifier = secrets.token_urlsafe(length)
    
    # 确保不包含 '.' 和 '~' 字符，只保留 RFC 7636 允许的字符
    allowed_chars = string.ascii_letters + string.digits + "-_"
    
    # 确保长度在 43-128 之间
    if length < 43:
        length = 43
    elif length > 128:
        length = 128
        
    # 生成随机字符串
    code_verifier = ''.join(secrets.choice(allowed_chars) for _ in range(length))
    return code_verifier

def generate_code_challenge(code_verifier):
    """根据 code_verifier 生成 code_challenge (S256 方法)"""
    # SHA256 哈希
    sha256_hash = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    # Base64 URL 编码，去除填充
    code_challenge = base64.urlsafe_b64encode(sha256_hash).decode('utf-8').rstrip('=')
    return code_challenge

def generate_state(length=32):
    """生成随机 state 字符串"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))
