# Polaris Auth gRPC Service

基于 Kiro Auth (AWS OIDC SSO) 的完整 OAuth 授权服务，自动完成 PKCE 交换流程。

## 核心功能

- 🚀 **批量生成授权 URL**：支持高并发生成，自动保存 state 映射
- 🔐 **自动 PKCE 交换**：收到回调时自动验证 state 并完成 token 交换
- ✅ **防 CSRF 攻击**：严格验证 state 参数
- 📦 **返回可用凭证**：客户端直接获取已交换的 OAuth 令牌
- 🪟 **Windows URI scheme**：自动注册 `kiro://` 协议处理

## 工作流程

```
1. 客户端调用 GenerateAuthURL/GenerateAuthURLs
   └─> 服务端生成授权 URL 并保存 state → code_verifier 映射

2. 用户在浏览器完成第三方登录
   └─> 浏览器重定向到 kiro://kiro.kiroAgent/authenticate-success?code=xxx&state=yyy

3. Windows 触发自定义协议，启动 auth-server -report "完整URL"
   └─> 服务端：
       - 解析 URL 提取 code 和 state
       - 验证 state（防 CSRF）
       - 使用对应的 code_verifier 完成 PKCE token 交换
       - 保存已交换的 OAuth 凭证

4. 客户端调用 FetchAndClearCallbacks
   └─> 获取所有已完成交换的 OAuth 凭证（access_token、refresh_token 等）
```

## 快速开始

### 启动服务器

```bash
make build
make run
# 或指定端口: ./bin/auth-server -port 50051
```

服务器启动后：
- 监听 gRPC 端口（默认 50051）
- Windows 上自动注册 `kiro://` 协议处理

## gRPC API

### GenerateAuthURL

生成单个授权 URL

**请求：**
```protobuf
message GenerateAuthURLRequest {
  string idp = 1;  // 身份提供商，首字母大写 (Google, Github, Gitlab)
}
```

**响应：**
```protobuf
message GenerateAuthURLResponse {
  string auth_url = 1;        // 授权URL
  string state = 2;           // state参数
  string code_verifier = 3;   // PKCE code verifier
  string code_challenge = 4;  // PKCE code challenge
}
```

### GenerateAuthURLs

批量生成授权 URL（并发执行）

**请求：**
```protobuf
message GenerateAuthURLsRequest {
  string idp = 1;   // 身份提供商，首字母大写 (Google, Github, Gitlab)
  int32 count = 2;  // 生成数量（1-1000）
}
```

**响应：**
```protobuf
message GenerateAuthURLsResponse {
  repeated GenerateAuthURLResponse urls = 1;  // URL列表
}
```

## 使用示例

### 使用 grpcurl 测试

```bash
# 生成单个授权URL（注意IDP首字母大写）
grpcurl -plaintext -d '{"idp":"Google"}' \
  localhost:50051 auth.AuthService/GenerateAuthURL

grpcurl -plaintext -d '{"idp":"Google"}'  localhost:50051 auth.AuthService\GenerateAuthURL

# 批量生成10个授权URL
grpcurl -plaintext -d '{"idp":"Github","count":10}' \
  localhost:50051 auth.AuthService/GenerateAuthURLs
```

### ReportCallback

**内部使用**：由 Windows URI scheme 触发，上报回调并自动完成 PKCE 交换。

**请求：**
```protobuf
message ReportCallbackRequest {
  string raw = 1;           // 完整的回调 URL
  int64 received_at = 2;    // 接收时间戳（毫秒）
}
```

**响应：**
```protobuf
message ReportCallbackResponse {
  bool ok = 1;
  string error = 2;         // 非空表示失败（如 state 验证失败）
}
```

### FetchAndClearCallbacks

**拉取所有已完成 PKCE 交换的 OAuth 凭证**，并清空存储。

**请求：**
```protobuf
message FetchAndClearCallbacksRequest {}
```

**响应：**
```protobuf
message FetchAndClearCallbacksResponse {
  repeated OAuthCredential credentials = 1;
}

message OAuthCredential {
  string access_token = 1;      // 访问令牌
  string refresh_token = 2;     // 刷新令牌
  string id_token = 3;          // ID 令牌
  string token_type = 4;        // 令牌类型（通常为 Bearer）
  int32 expires_in = 5;         // 过期时间（秒）
  string profile_arn = 6;       // Profile ARN
  int64 received_at = 7;        // 接收时间戳（毫秒）
  string state = 8;             // 原始 state（用于客户端关联）
}
```

## 使用示例

### 完整流程示例

```bash
# 1. 生成授权 URL
grpcurl -plaintext -d '{"idp":"Google"}' \
  localhost:50051 auth.AuthService/GenerateAuthURL

# 响应示例：
# {
#   "authUrl": "https://prod.us-east-1.auth.desktop.kiro.dev/login?...",
#   "state": "EVb7GbAX3whRNBfnkcNsHw",
#   "codeVerifier": "ss-QB1mks31x3UeleN9y2Dr_S7NJx30ZjLolT8vv95I",
#   "codeChallenge": "n8kHSh7ZHFm1YSeEbC-s4l_JN6CyfYusljcLiaXEElE"
# }

# 2. 用户在浏览器中访问 authUrl 完成登录
#    浏览器自动重定向到 kiro://... 触发回调
#    服务端自动完成 PKCE 交换

# 3. 获取已交换的 OAuth 凭证
grpcurl -plaintext -d '{}' \
  localhost:50051 auth.AuthService/FetchAndClearCallbacks

# 响应示例：
# {
#   "credentials": [
#     {
#       "accessToken": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
#       "refreshToken": "v1.MRqPxaBmYzjm...",
#       "idToken": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
#       "tokenType": "Bearer",
#       "expiresIn": 3600,
#       "profileArn": "arn:aws:iam::...",
#       "receivedAt": "1699876543210",
#       "state": "EVb7GbAX3whRNBfnkcNsHw"
#     }
#   ]
# }
```

### 批量生成示例

```bash
# 批量生成 10 个授权 URL
grpcurl -plaintext -d '{"idp":"Github","count":10}' \
  localhost:50051 auth.AuthService/GenerateAuthURLs
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

### 客户端实现

本项目**仅提供 gRPC 服务端**，不包含客户端实现。开发者需要根据 `proto/auth.proto` 定义自行实现客户端，支持任何语言（Go、Python、Java、JavaScript 等）。

## License

MIT