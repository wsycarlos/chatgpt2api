<h1 align="center">ChatGPT2API</h1>


<p align="center">ChatGPT2API 主要是对 ChatGPT 官网相关能力进行逆向整理与封装，提供面向 ChatGPT 图片生成、图片编辑、多图组图编辑场景的 OpenAI 兼容图片 API / 代理，并集成在线画图、个人账号 OAuth 登录与 Docker 自托管部署能力。</p>

> [!WARNING]
> 免责声明：
>
> 本项目涉及对 ChatGPT 官网文本生成、图片生成与图片编辑等相关接口的逆向研究，仅供个人学习、技术研究与非商业性技术交流使用。
>
> - 严禁将本项目用于任何商业用途、盈利性使用、批量操作、自动化滥用或规模化调用。
> - 严禁将本项目用于破坏市场秩序、恶意竞争、套利倒卖、二次售卖相关服务，以及任何违反 OpenAI 服务条款或当地法律法规的行为。
> - 严禁将本项目用于生成、传播或协助生成违法、暴力、色情、未成年人相关内容，或用于诈骗、欺诈、骚扰等非法或不当用途。
> - 使用者应自行承担全部风险，包括但不限于账号被限制、临时封禁或永久封禁以及因违规使用等所导致的法律责任。
> - 使用本项目即视为你已充分理解并同意本免责声明全部内容；如因滥用、违规或违法使用造成任何后果，均由使用者自行承担。
> - 本项目基于对 ChatGPT 官网相关能力的逆向研究实现，存在账号受限、临时封禁或永久封禁的风险。请勿使用你自己的重要账号、常用账号或高价值账号进行测试。

## 快速开始

### Docker 运行（推荐）

```bash
git clone git@github.com:basketikun/chatgpt2api.git
cd chatgpt2api
# 设置登录密钥：编辑 config.json 中的 auth-key，或在 docker-compose.yml 中设置 CHATGPT2API_AUTH_KEY
docker compose up -d --build
```

- Web 面板：`http://localhost:3000`
- API 地址：`http://localhost:3000/v1`
- 数据目录：`./data`

> 注意：默认镜像 `ghcr.io/basketikun/chatgpt2api:latest` 为旧版号池架构。如果你正在使用本分支的个人账号模式，请务必加 `--build` 使用本地 Dockerfile 构建。

### 本地开发

启动后端：

```bash
git clone git@github.com:basketikun/chatgpt2api.git
cd chatgpt2api
uv sync
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --access-log
```

启动前端：

```bash
cd chatgpt2api/web
bun install
bun run dev
```

然后打开 `http://localhost:3000`，用 `config.json` 中设置的 `auth-key` 登录管理员账号。

### 更新新版本

```bash
git pull
docker compose down
docker compose up -d --build
```

## 账号登录方式

本项目已切换到**个人账号模式**，不再提供自动注册、号池、CPA/Sub2API 导入等功能。支持以下两种方式添加你的 ChatGPT 订阅账号：

### 1. 浏览器 OAuth 登录（推荐）

进入 Web 面板的「账号管理」页面：

1. 点击 **添加 ChatGPT 账号**。
2. （可选）填写你的 ChatGPT 邮箱，登录页会预填。
3. 点击 **打开授权页面**，系统会在新标签页打开 OpenAI OAuth 授权链接。
4. 在 OpenAI 页面登录你的 ChatGPT 订阅账号。
5. 登录成功后，浏览器地址栏会显示类似 `https://platform.openai.com/auth/callback?code=...&state=...` 的 URL。
6. 复制完整 callback URL，粘回对话框的输入框。
7. 点击 **完成添加**，后端会自动换取并保存 `access_token`、`refresh_token`、`id_token`。

添加成功后，系统会自动使用默认账号调用 ChatGPT 官网接口。你也可以添加 1–5 个账号并手动切换默认账号。

### 2. 导入 Access Token

如果你已经有 OpenAI/ChatGPT 的 `access_token`，也可以在「账号管理」页点击 **导入 Token**，每行一个粘贴进去。

> 注意：`refresh_token` 过期后无法自动续期，建议优先使用 OAuth 登录。

## 存储后端配置

支持通过环境变量 `STORAGE_BACKEND` 切换存储方式：

- `json` - 本地 JSON 文件（默认）
- `sqlite` - 本地 SQLite 数据库
- `postgres` - 外部 PostgreSQL（需配置 `DATABASE_URL`）
- `git` - Git 私有仓库（需配置 `GIT_REPO_URL` 和 `GIT_TOKEN`）

示例：使用 PostgreSQL

```yaml
environment:
  - STORAGE_BACKEND=postgres
  - DATABASE_URL=postgresql://user:password@host:5432/dbname
```

## 功能

### API 兼容能力

- 兼容 `POST /v1/images/generations` 图片生成接口
- 兼容 `POST /v1/images/edits` 图片编辑接口
- 兼容面向图片场景的 `POST /v1/chat/completions`
- 兼容面向图片场景的 `POST /v1/responses`
- `GET /v1/models` 返回 `gpt-image-2`、`codex-gpt-image-2`、`auto`、`gpt-5`、`gpt-5-1`、`gpt-5-2`、`gpt-5-3`、`gpt-5-3-mini`、
  `gpt-5-mini`
- 支持通过 `n` 返回多张生成结果
- 支持生成可编辑 PPT 文件
- 支持生成可编辑 PSD 文件
- 支持 Codex 中的画图接口逆向，仅 `Plus` / `Team` / `Pro` 订阅可用，模型别名为 `codex-gpt-image-2`，如有需要可自行在其他场景映射回
  `gpt-image-2`，用于和官网画图区分；也就意味着同一账号会同时有官网和 Codex 两份生图额度

### 在线画图功能

- 内置在线画图工作台，支持生成、图片编辑与多图组图编辑
- 支持 `gpt-image-2`、`codex-gpt-image-2`、`auto`、`gpt-5`、`gpt-5-1`、`gpt-5-2`、`gpt-5-3`、`gpt-5-3-mini`、`gpt-5-mini` 模型选择
- 编辑模式支持参考图上传
- 前端支持多图生成交互
- 本地保存图片会话历史，支持回看、删除和清空
- 支持服务端缓存图片URL
- 图片生成进度追踪，超时后可继续等待
- 图片懒加载与滚动位置记忆，优化大量图片场景性能

### 账号管理功能

- 通过浏览器 OAuth 登录添加个人 ChatGPT 账号
- 支持导入已有 Access Token
- 支持设置默认账号
- 支持删除账号

## 效果展示

<table width="100%">
  <tr>
    <td width="50%"><img src="https://i.ibb.co/Jj8nfwwP/image.png" alt="image" border="0"></td>
    <td width="50%"><img src="https://i.ibb.co/pqf235v/image-edit.png" alt="image edit" border="0"></td>
  </tr>
  <tr>
    <td width="50%"><img src="https://i.ibb.co/tPcqtVfd/chery-studio.png" alt="chery studio" border="0"></td>
    <td width="50%"><img src="https://i.ibb.co/PsT9YHBV/account-pool.png" alt="account pool" border="0"></td>
  </tr>
  <tr>
    <td width="50%"><img src="https://i.ibb.co/rRWLG08q/new-api.png" alt="new api" border="0"></td>
  </tr>
</table>

## API

所有 AI 接口都需要请求头：

```http
Authorization: Bearer <auth-key>
```

<details>
<summary><code>GET /v1/models</code></summary>
<br>

返回当前暴露的图片模型列表。

```bash
curl http://localhost:8000/v1/models \
  -H "Authorization: Bearer <auth-key>"
```

<details>
<summary>说明</summary>
<br>

| 字段   | 说明                                                                                                         |
|:-----|:-----------------------------------------------------------------------------------------------------------|
| 返回模型 | `gpt-image-2`、`codex-gpt-image-2`、`auto`、`gpt-5`、`gpt-5-1`、`gpt-5-2`、`gpt-5-3`、`gpt-5-3-mini`、`gpt-5-mini` |
| 接入场景 | 可接入 Cherry Studio、New API 等上游或客户端                                                                          |

<br>
</details>
</details>

<details>
<summary><code>POST /v1/images/generations</code></summary>
<br>

OpenAI 兼容图片生成接口，用于文生图。

```bash
curl http://localhost:8000/v1/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <auth-key>" \
  -d '{
    "model": "gpt-image-2",
    "prompt": "一只在草地上奔跑的柴犬",
    "size": "1024x1536",
    "quality": "high",
    "n": 1
  }'
```

</details>

<details>
<summary><code>POST /v1/images/edits</code></summary>
<br>

OpenAI 兼容图片编辑接口，支持参考图编辑与多图组图编辑。

```bash
curl http://localhost:8000/v1/images/edits \
  -H "Authorization: Bearer <auth-key>" \
  -F "image=@ref.png" \
  -F "model=gpt-image-2" \
  -F "prompt=把这只狗换成太空背景" \
  -F "size=1024x1536"
```

</details>

<details>
<summary><code>POST /v1/chat/completions</code></summary>
<br>

面向图片场景的 Chat Completions 兼容接口，可用于支持图片生成的客户端。

</details>

<details>
<summary><code>POST /v1/responses</code></summary>
<br>

面向图片场景的 Responses 兼容接口。

</details>

## 项目结构

```
.
├── api/                # FastAPI 路由
├── services/           # 业务服务
│   ├── personal_account_service.py   # 个人账号管理
│   ├── oauth_login_service.py        # OAuth 登录桥
│   ├── protocol/       # OpenAI / Anthropic 协议适配
│   └── storage/        # 存储后端抽象
├── web/                # Next.js 前端
├── utils/              # 工具函数
├── test/               # 测试用例
├── Dockerfile
├── docker-compose.yml
└── config.json
```

## 许可证

MIT
