
# Polaris Auth Service (Python HTTP版本)

基于 Kiro Auth (AWS OIDC SSO) 的完整 OAuth 授权服务，自动完成 PKCE 交换流程。

## 核心功能

- 🚀 **批量生成授权 URL**：支持高并发生成，自动保存 state 映射
- 🔐 **自动 PKCE 交换**：收到回调时自动验证 state 并完成 token 交换
- ✅ **防 CSRF 攻击**：严格验证 state 参数
- 📦 **返回可用凭证**：客户端直接获取已交换的 OAuth 令牌
- 🪟 **Windows URI scheme**：自动注册 `kiro://` 协议处理

## 技术栈

- FastAPI：高性能 Python Web 框架
- SQLite：轻量级数据库，用于存储 state 映射和 OAuth 凭证
- Python 3.8+：推荐使用 Python 3.8 或更高版本

## 安装与启动

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务

Windows用户：
```bash
start.bat
```

或直接运行：
```bash
python main.py
```

服务默认将在 `http://localhost:8000` 启动。

## API 接口

### 1. 生成单个授权 URL

**端点**: `POST /generate-auth-url`

**请求体**:
```json
{
  "idp": "Google"  // 身份提供商，首字母大写 (Google, Github, Gitlab)
}
```

**响应**:
```json
{
  "auth_url": "https://prod.us-east-1.auth.desktop.kiro.dev/login?...",
  "state": "EVb7GbAX3whRNBfnkcNsHw",
  "code_verifier": "ss-QB1mks31x3UeleN9y2Dr_S7NJx30ZjLolT8vv95I",
  "code_challenge": "n8kHSh7ZHFm1YSeEbC-s4l_JN6CyfYusljcLiaXEElE"
}
```

**示例**:
```bash
curl -X POST "http://localhost:8000/generate-auth-url"      -H "Content-Type: application/json"      -d '{"idp":"Google"}'
```

### 2. 批量生成授权 URL

**端点**: `POST /generate-auth-urls`

**请求体**:
```json
{
  "idp": "Github",  // 身份提供商，首字母大写 (Google, Github, Gitlab)
  "count": 10       // 生成数量（1-1000）
}
```

**响应**:
```json
{
  "urls": [
    {
      "auth_url": "https://prod.us-east-1.auth.desktop.kiro.dev/login?...",
      "state": "EVb7GbAX3whRNBfnkcNsHw",
      "code_verifier": "ss-QB1mks31x3UeleN9y2Dr_S7NJx30ZjLolT8vv95I",
      "code_challenge": "n8kHSh7ZHFm1YSeEbC-s4l_JN6CyfYusljcLiaXEElE"
    },
    // 更多URL...
  ]
}
```

**示例**:
```bash
curl -X POST "http://localhost:8000/generate-auth-urls"      -H "Content-Type: application/json"      -d '{"idp":"Github","count":10}'
```

### 3. 上报回调

**端点**: `POST /report-callback`

**请求体**:
```json
{
  "raw": "kiro://kiro.kiroAgent/authenticate-success?code=xxx&state=yyy",  // 完整的回调 URL
  "received_at": 1699876543210  // 接收时间戳（毫秒）
}
```

**响应**:
```json
{
  "ok": true,
  "error": ""  // 非空表示失败（如 state 验证失败）
}
```

**示例**:
```bash
curl -X POST "http://localhost:8000/report-callback"      -H "Content-Type: application/json"      -d '{"raw":"kiro://kiro.kiroAgent/authenticate-success?code=xxx&state=yyy","received_at":1699876543210}'
```

### 4. 获取并清空凭证

**端点**: `GET /fetch-and-clear-callbacks`

**响应**:
```json
{
  "credentials": [
    {
      "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
      "refresh_token": "v1.MRqPxaBmYzjm...",
      "id_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
      "token_type": "Bearer",
      "expires_in": 3600,
      "profile_arn": "arn:aws:iam::...",
      "received_at": 1699876543210,
      "state": "EVb7GbAX3whRNBfnkcNsHw"
    }
    // 更多凭证...
  ]
}
```

**示例**:
```bash
curl -X GET "http://localhost:8000/fetch-and-clear-callbacks"
```

## 工作流程

```
1. 客户端调用 /generate-auth-url 或 /generate-auth-urls
   └─> 服务端生成授权 URL 并保存 state → code_verifier 映射

2. 用户在浏览器完成第三方登录
   └─> 浏览器重定向到 kiro://kiro.kiroAgent/authenticate-success?code=xxx&state=yyy

3. Windows 触发自定义协议，启动 auth-server -report "完整URL"
   └─> 服务端：
       - 解析 URL 提取 code 和 state
       - 验证 state（防 CSRF）
       - 使用对应的 code_verifier 完成 PKCE token 交换
       - 保存已交换的 OAuth 凭证

4. 客户端调用 /fetch-and-clear-callbacks
   └─> 获取所有已完成交换的 OAuth 凭证（access_token、refresh_token 等）
```

## 故障排除

### State 验证失败

- 原因：state 过期或未生成
- 解决：确保在同一服务器实例中生成 URL 并接收回调

### Token 交换失败

- 检查网络连接到 `prod.us-east-1.auth.desktop.kiro.dev`
- 确认 code 未过期（通常 10 分钟有效期）
- 验证 redirect_uri 完全一致

### IDP 参数格式

**IDP（身份提供商）参数必须首字母大写**，例如：
- ✅ `Google`
- ✅ `Github`
- ✅ `Gitlab`
- ❌ `google` (错误)
- ❌ `github` (错误)

## 开发说明

### 数据库

应用使用 SQLite 数据库存储 state 映射和 OAuth 凭证。数据库文件 `polaris_auth.db` 会在首次运行时自动创建。

### 日志

应用使用 Python 标准日志库记录重要事件。日志级别可在 `main.py` 中配置。

### 自定义配置

可以通过修改 `main.py` 中的以下常量来自定义应用行为：

```python
KIRO_AUTH_DOMAIN = "prod.us-east-1.auth.desktop.kiro.dev"  # Kiro Auth 域名
STATE_EXPIRY = 10 * 60  # state 过期时间（秒）
CODE_EXPIRY = 10 * 60  # code 过期时间（秒）
```

## License

MIT
