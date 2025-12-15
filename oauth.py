import requests
import json
import urllib.parse
from datetime import datetime
from typing import Dict, Optional, Tuple

# Kiro Auth 域名
KIRO_AUTH_DOMAIN = "prod.us-east-1.auth.desktop.kiro.dev"

# IDP 配置
IDP_CONFIG = {
    "Google": {
        "auth_endpoint": f"https://{KIRO_AUTH_DOMAIN}/login",
        "token_endpoint": f"https://{KIRO_AUTH_DOMAIN}/oauth/token",
        "redirect_uri": "kiro://kiro.kiroAgent/authenticate-success",
        "scope": "openid profile email"
    },
    "Github": {
        "auth_endpoint": f"https://{KIRO_AUTH_DOMAIN}/login",
        "token_endpoint": f"https://{KIRO_AUTH_DOMAIN}/oauth/token",
        "redirect_uri": "kiro://kiro.kiroAgent/authenticate-success",
        "scope": "openid profile email"
    },
    "Gitlab": {
        "auth_endpoint": f"https://{KIRO_AUTH_DOMAIN}/login",
        "token_endpoint": f"https://{KIRO_AUTH_DOMAIN}/oauth/token",
        "redirect_uri": "kiro://kiro.kiroAgent/authenticate-success",
        "scope": "openid profile email"
    }
}

def generate_auth_url(idp: str, state: str, code_challenge: str) -> str:
    """生成授权 URL"""
    if idp not in IDP_CONFIG:
        raise ValueError(f"不支持的 IDP: {idp}")

    config = IDP_CONFIG[idp]

    params = {
        "client_id": "kiro-agent",
        "redirect_uri": config["redirect_uri"],
        "response_type": "code",
        "scope": config["scope"],
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "idp": idp
    }

    # 使用 URL 编码确保参数正确传递
    query_string = urllib.parse.urlencode(params)
    return f"{config['auth_endpoint']}?{query_string}"

def exchange_code_for_token(code: str, code_verifier: str, idp: str) -> Dict:
    """使用授权码和 code_verifier 交换 access_token"""
    if idp not in IDP_CONFIG:
        raise ValueError(f"不支持的 IDP: {idp}")

    config = IDP_CONFIG[idp]

    # 使用下划线命名法，与kiro-batch-login保持一致
    json_data = {
        "code": code,
        "code_verifier": code_verifier,
        "redirect_uri": config["redirect_uri"]
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "KiroBatchLoginCLI/1.0.0"  # 使用与kiro-batch-login相同的User-Agent
    }

    try:
        # 添加调试日志
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Exchanging code for token with IDP: {idp}")
        logger.info(f"Token endpoint: {config['token_endpoint']}")
        logger.info(f"Request data: {json_data}")
        
        # 使用 JSON 格式
        logger.info(f"JSON data: {json_data}")
        logger.info(f"Headers: {headers}")
        
        # 打印请求的详细信息
        import json
        logger.info(f"Request body: {json.dumps(json_data)}")
        
        # 使用kiro-batch-login的token端点
        token_endpoint = f"https://{KIRO_AUTH_DOMAIN}/oauth/token"
        response = requests.post(
            token_endpoint,
            json=json_data,  # 使用 json 参数
            headers=headers,
            timeout=30
        )
        
        # 添加响应调试日志
        logger.info(f"Response status: {response.status_code}")
        logger.info(f"Response body: {response.text}")

        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        # 更详细的错误信息
        error_msg = f"Token exchange failed: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            error_msg += f"\nResponse status: {e.response.status_code}"
            error_msg += f"\nResponse body: {e.response.text}"
        raise Exception(error_msg)

def parse_callback_url(url: str) -> Tuple[str, str]:
    """解析回调 URL，提取 code 和 state"""
    # 提取查询参数
    if "?" not in url:
        raise ValueError("无效的回调 URL: 缺少查询参数")

    query_string = url.split("?", 1)[1]
    params = {}

    for param in query_string.split("&"):
        if "=" in param:
            key, value = param.split("=", 1)
            params[key] = value

    if "code" not in params:
        raise ValueError("回调 URL 缺少 code 参数")

    if "state" not in params:
        raise ValueError("回调 URL 缺少 state 参数")

    return params["code"], params["state"]
