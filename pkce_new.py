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

    # 使用更简单的字符集生成 code_verifier
    # 只包含字母和数字，避免特殊字符
    allowed_chars = string.ascii_letters + string.digits
    
    # 生成随机字符串
    code_verifier = ''.join(secrets.choice(allowed_chars) for _ in range(length))

    # 确保长度符合要求
    while len(code_verifier) < 43:
        code_verifier += secrets.choice(allowed_chars)

    if len(code_verifier) > 128:
        code_verifier = code_verifier[:128]

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
