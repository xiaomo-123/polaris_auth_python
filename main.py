import logging
from datetime import datetime
from typing import List, Dict, Any
import os
import sys

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from contextlib import asynccontextmanager

from models import get_db, StateMapping, OAuthCredential
from pkce_new import generate_code_verifier, generate_code_challenge, generate_state
from oauth import generate_auth_url, exchange_code_for_token, parse_callback_url
from sqlalchemy.orm import Session

# 配置日志
# 解决Windows下中文编码问题
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())

# 创建自定义日志处理器，处理中文字符
class CustomStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            msg = self.format(record) + self.terminator
            self.stream.write(msg)
            self.flush()
        except Exception:
            self.handleError(record)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        CustomStreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Windows URI scheme 处理
def register_uri_scheme():
    """注册 Windows URI scheme"""
    if sys.platform == "win32":
        try:
            import winreg

            # 注册表路径
            key_path = r"SOFTWARE\Classes\kiro"

            # 创建或打开注册表项
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
            winreg.SetValue(key, None, winreg.REG_SZ, "URL:kiro Protocol")
            winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")

            # 创建命令项
            command_key = winreg.CreateKey(key, r"shell\open\command")
            winreg.SetValue(command_key, None, winreg.REG_SZ, 
                          f'"{sys.executable}" "{os.path.abspath(__file__)}" -report "%1"')

            # 关闭注册表项
            winreg.CloseKey(key)
            winreg.CloseKey(command_key)

            logger.info("Successfully registered kiro:// URI scheme")

        except Exception as e:
            logger.error(f"Failed to register URI scheme: {str(e)}")

# 使用lifespan事件处理器替代已弃用的on_event
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时注册 URI scheme
    register_uri_scheme()
    
    # 确保数据库表已创建
    from models import Base, engine
    Base.metadata.create_all(bind=engine)
    
    yield
    # 应用关闭时的清理工作（如果需要）

# FastAPI 应用
app = FastAPI(
    title="Polaris Auth Service",
    description="基于 Kiro Auth (AWS OIDC SSO) 的完整 OAuth 授权服务，自动完成 PKCE 交换流程",
    version="1.0.0",
    lifespan=lifespan
)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic 模型
class GenerateAuthURLRequest(BaseModel):
    idp: str  # 身份提供商，首字母大写 (Google, Github, Gitlab)

class GenerateAuthURLResponse(BaseModel):
    auth_url: str        # 授权URL
    state: str           # state参数
    code_verifier: str   # PKCE code verifier
    code_challenge: str  # PKCE code challenge

class GenerateAuthURLsRequest(BaseModel):
    idp: str   # 身份提供商，首字母大写 (Google, Github, Gitlab)
    count: int  # 生成数量（1-1000）

class GenerateAuthURLsResponse(BaseModel):
    urls: List[GenerateAuthURLResponse]  # URL列表

class ReportCallbackRequest(BaseModel):
    raw: str           # 完整的回调 URL
    received_at: int    # 接收时间戳（毫秒）

class ReportCallbackResponse(BaseModel):
    ok: bool
    error: str         # 非空表示失败（如 state 验证失败）

class OAuthCredentialResponse(BaseModel):
    access_token: str      # 访问令牌
    refresh_token: str     # 刷新令牌
    id_token: str          # ID 令牌
    token_type: str        # 令牌类型（通常为 Bearer）
    expires_in: int         # 过期时间（秒）
    profile_arn: str       # Profile ARN
    received_at: int        # 接收时间戳（毫秒）
    state: str             # 原始 state（用于客户端关联）

class FetchAndClearCallbacksResponse(BaseModel):
    credentials: List[OAuthCredentialResponse]

# API 路由
@app.post("/generate-auth-url", response_model=GenerateAuthURLResponse)
async def generate_auth_url_endpoint(
    request: GenerateAuthURLRequest,
    db: Session = Depends(get_db)
):
    """生成单个授权 URL"""
    idp = request.idp

    # 验证 IDP 参数
    if idp not in ["Google", "Github", "Gitlab"]:
        raise HTTPException(status_code=400, detail=f"不支持的 IDP: {idp}")

    # 生成 PKCE 参数
    state = generate_state()
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    # 生成授权 URL
    auth_url = generate_auth_url(idp, state, code_challenge)

    # 保存 state 映射
    state_mapping = StateMapping(
        state=state,
        code_verifier=code_verifier,
        idp=idp
    )
    db.add(state_mapping)
    db.commit()

    logger.info(f"Generated auth URL: IDP={idp}, State={state}")

    return GenerateAuthURLResponse(
        auth_url=auth_url,
        state=state,
        code_verifier=code_verifier,
        code_challenge=code_challenge
    )

@app.post("/generate-auth-urls", response_model=GenerateAuthURLsResponse)
async def generate_auth_urls_endpoint(
    request: GenerateAuthURLsRequest,
    db: Session = Depends(get_db)
):
    """批量生成授权 URL（并发执行）"""
    idp = request.idp
    count = request.count

    # 验证参数
    if idp not in ["Google", "Github", "Gitlab"]:
        raise HTTPException(status_code=400, detail=f"不支持的 IDP: {idp}")

    if count < 1 or count > 1000:
        raise HTTPException(status_code=400, detail="count 必须在 1-1000 之间")

    # 批量生成
    urls = []
    for _ in range(count):
        # 生成 PKCE 参数
        state = generate_state()
        code_verifier = generate_code_verifier()
        code_challenge = generate_code_challenge(code_verifier)

        # 生成授权 URL
        auth_url = generate_auth_url(idp, state, code_challenge)

        # 保存 state 映射
        state_mapping = StateMapping(
            state=state,
            code_verifier=code_verifier,
            idp=idp
        )
        db.add(state_mapping)

        # 添加到结果列表
        urls.append(GenerateAuthURLResponse(
            auth_url=auth_url,
            state=state,
            code_verifier=code_verifier,
            code_challenge=code_challenge
        ))

    db.commit()

    logger.info(f"Batch generated auth URLs: IDP={idp}, Count={count}")

    return GenerateAuthURLsResponse(urls=urls)

@app.post("/report-callback", response_model=ReportCallbackResponse)
async def report_callback_endpoint(
    request: ReportCallbackRequest,
    db: Session = Depends(get_db)
):
    """内部使用：由 Windows URI scheme 触发，上报回调并自动完成 PKCE 交换"""
    raw_url = request.raw
    received_at = request.received_at

    try:
        # 解析回调 URL
        code, state = parse_callback_url(raw_url)

        # 查找 state 映射
        state_mapping = db.query(StateMapping).filter(StateMapping.state == state).first()

        if not state_mapping:
            logger.warning(f"State validation failed: State={state} not found")
            return ReportCallbackResponse(
                ok=False,
                error=f"无效的 state: {state}"
            )

        # 检查是否过期
        if state_mapping.is_expired():
            logger.warning(f"State validation failed: State={state} has expired")
            return ReportCallbackResponse(
                ok=False,
                error=f"state 已过期: {state}"
            )

        # 使用 code_verifier 交换 token
        try:
            token_data = exchange_code_for_token(
                code=code,
                code_verifier=state_mapping.code_verifier,
                idp=state_mapping.idp
            )
        except Exception as e:
            logger.error(f"Token exchange failed: {str(e)}")
            return ReportCallbackResponse(
                ok=False,
                error=f"Token 交换失败: {str(e)}"
            )

        # 保存 OAuth 凭证
        oauth_credential = OAuthCredential(
            state=state,
            access_token=token_data.get("access_token", ""),
            refresh_token=token_data.get("refresh_token"),
            id_token=token_data.get("id_token"),
            token_type=token_data.get("token_type", "Bearer"),
            expires_in=token_data.get("expires_in"),
            profile_arn=token_data.get("profile_arn"),
            received_at=datetime.fromtimestamp(received_at / 1000) if received_at else datetime.utcnow(),
            idp=state_mapping.idp
        )
        db.add(oauth_credential)

        # 删除 state 映射
        db.delete(state_mapping)

        db.commit()

        logger.info(f"Callback processed successfully: State={state}, IDP={state_mapping.idp}")

        return ReportCallbackResponse(
            ok=True,
            error=""
        )

    except Exception as e:
        logger.error(f"Callback processing failed: {str(e)}")
        return ReportCallbackResponse(
            ok=False,
            error=f"回调处理失败: {str(e)}"
        )

@app.get("/fetch-and-clear-callbacks", response_model=FetchAndClearCallbacksResponse)
async def fetch_and_clear_callbacks_endpoint(db: Session = Depends(get_db)):
    """拉取所有已完成 PKCE 交换的 OAuth 凭证，并清空存储"""
    # 查询所有凭证
    credentials = db.query(OAuthCredential).all()

    # 转换为响应模型
    credential_responses = []
    for cred in credentials:
        credential_responses.append(OAuthCredentialResponse(
            access_token=cred.access_token,
            refresh_token=cred.refresh_token or "",
            id_token=cred.id_token or "",
            token_type=cred.token_type,
            expires_in=cred.expires_in or 0,
            profile_arn=cred.profile_arn or "",
            received_at=int(cred.received_at.timestamp() * 1000),
            state=cred.state
        ))

    # 清空凭证表
    db.query(OAuthCredential).delete()
    db.commit()

    logger.info(f"Returned and cleared {len(credential_responses)} credentials")

    return FetchAndClearCallbacksResponse(credentials=credential_responses)

# 命令行处理
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Polaris Auth Service")
    parser.add_argument("-port", type=int, default=8000, help="服务器端口")
    parser.add_argument("-report", type=str, help="报告回调 URL")

    args = parser.parse_args()

    # 如果提供了 -report 参数，处理回调
    if args.report:
        import requests

        try:
            # 发送回调到本地服务器
            response = requests.post(
                f"http://localhost:{args.port}/report-callback",
                json={
                    "raw": args.report,
                    "received_at": int(datetime.now().timestamp() * 1000)
                },
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    print("回调处理成功")
                else:
                    print(f"回调处理失败: {result.get('error')}")
            else:
                print(f"请求失败: {response.status_code}")

        except Exception as e:
            print(f"处理回调时出错: {str(e)}")

        sys.exit(0)

    # 启动服务器
    uvicorn.run(app, host="0.0.0.0", port=args.port)
