# Leaflow 自动签到脚本

这是一个用于在 [Leaflow](https://leaflow.net/) 网站上自动执行每日签到的 Python 脚本。支持 GitHub Actions 自动运行和本地运行。

## ✨ 主要功能

- **多账号支持**：通过环境变量轻松管理多个 Leaflow 账号。
- **自动签到**：模拟浏览器操作，自动完成每日签到，赚取奖励。
- **余额查询**：自动获取并显示每个账号的当前余额。
- **Telegram 通知**：通过 Telegram Bot 发送签到结果通知。
- **GitHub Actions 集成**：支持通过 GitHub Actions 实现每日定时自动签到。
- **防检测机制**：使用新版无头模式和自定义 User-Agent，有效绕过网站检测。
- **稳健运行**：内置重试机制、超时处理和错误恢复，确保签到成功率。

## 签到入口变更说明

- 由于官方路由调整，原 `https://checkin.leaflow.net` 在部分地区可能超时。
- 当前签到入口位于主站工作空间页面：`https://leaflow.net/workspaces`，点击“签到试用”弹窗后再点“立即签到”。
- 脚本已支持从工作空间弹窗签到，并支持自定义签到入口：
  - `LEAFLOW_CHECKIN_URL`：单个 URL。
  - `LEAFLOW_CHECKIN_URLS`：多个 URL（逗号分隔，按顺序尝试）。
- 若访问不稳定，建议将主站入口放在 `LEAFLOW_CHECKIN_URLS` 的第一位。

## 🚀 快速开始 (GitHub Actions)

最简单的方式是使用 GitHub Actions 进行每日自动签到，无需本地环境。

### 1. Fork 本仓库

点击本页面右上角的 **Fork** 按钮，将此仓库复制到你自己的 GitHub 账号下。

### 2. 设置 Secrets

在你 Fork 的仓库页面，点击 **Settings** -> **Secrets and variables** -> **Actions**，然后点击 **New repository secret** 添加以下密钥：

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `LEAFLOW_ACCOUNTS` | 账号列表（邮箱:密码），多账号用英文逗号分隔 | `test1@gmail.com:pass1,test2@gmail.com:pass2` |
| `LEAFLOW_EMAIL` | 单账号邮箱（可选，优先级低于 ACCOUNTS） | `test@gmail.com` |
| `LEAFLOW_PASSWORD` | 单账号密码（可选） | `password123` |
| `LEAFLOW_COOKIE` | （**推荐**）直接使用 Cookie 登录，跳过账号密码登录 | `remember_web_xxx=...; session=...` |
| `LEAFLOW_CHECKIN_URL` | 自定义签到地址（可选） | `https://checkin.leaflow.net` |
| `LEAFLOW_CHECKIN_URLS` | 多个签到地址，用逗号分隔（可选） | `https://checkin.leaflow.net,https://...` |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token（可选） | `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11` |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID（可选） | `123456789` |

### 🚀 2026/02 优化更新
针对 Leaflow 近期访问不稳定的问题，脚本进行了以下优化：
1. **Cookie 登录支持**：推荐使用 `LEAFLOW_COOKIE` 环境变量，直接跳过登录步骤，规避登录页面的验证码和加载卡顿。
2. **加速加载**：自动屏蔽 reCAPTCHA、Google Fonts 等非核心资源，显著提升页面加载速度。
3. **工作空间弹窗签到**：优先尝试在主站工作空间（workspaces）页面通过弹窗签到，成功率更高。
4. **智能重试**：增强了超时处理和重试机制，适应不稳定的网络环境。

### 3. 启用 GitHub Actions

在你 Fork 的仓库页面，点击 **Actions** 选项卡，然后点击 **I understand my workflows, go ahead and enable them** 启用工作流。

### 4. 运行测试

1.  在 **Actions** 页面，点击左侧的 **Leaflow Auto Checkin** 工作流。
2.  点击右侧的 **Run workflow** 下拉菜单，点击绿色的 **Run workflow** 按钮。
3.  等待运行完成，查看日志确认是否签到成功。

此后，脚本将在每天 UTC 时间 01:15（北京时间 09:15）自动运行。

## 账号配置（单/多账号）

支持两种配置方式：

**多账号（推荐）**
- 使用 `LEAFLOW_ACCOUNTS`，格式：`邮箱1:密码1,邮箱2:密码2`

**单账号**
- 使用 `LEAFLOW_EMAIL` + `LEAFLOW_PASSWORD`

说明：两种方式任选其一即可，优先使用 `LEAFLOW_ACCOUNTS`。

## Docker 部署（推荐）

构建镜像（支持语义化 tag，例如 1.0.0）：
```bash
docker build -t leaflow-auto-checkin:latest .
```

### Docker 环境变量说明

| 变量名 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| `LEAFLOW_ACCOUNTS` | 多账号配置 (email:pass,email2:pass2) | 无 | 否 (与 Cookie 二选一) |
| `LEAFLOW_COOKIE` | Cookie 登录配置 (key=value;...) | 无 | 否 (推荐) |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | 无 | 否 |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID | 无 | 否 |
| `LEAFLOW_CHECKIN_URLS` | 自定义签到地址 (逗号分隔) | 自动探测 | 否 |
| `DB_PATH` | SQLite 数据库路径 | `/app/data/leaflow.db` | 否 |
| `ADMIN_TOKEN` | Web 面板访问令牌 (安全验证) | 无 | 否 |
| `PORT` | Web 服务端口 | `8080` | 否 |

### 运行示例

**方式一：使用 Docker Compose (推荐)**
```bash
# 启动服务（包含 Web 面板）
docker compose up -d
```
启动后访问：`http://localhost:8080`

**方式二：使用 Docker Run (仅脚本)**

Cookie 登录运行：
```bash
docker run --rm \
  -e LEAFLOW_COOKIE="remember_web_xxx=...; session=..." \
  leaflow-auto-checkin:latest
```

多账号运行：
```bash
docker run --rm \
  -e LEAFLOW_ACCOUNTS="email1:password1,email2:password2" \
  -e TELEGRAM_BOT_TOKEN="xxx" \
  -e TELEGRAM_CHAT_ID="xxx" \
  leaflow-auto-checkin:latest
```

## 可视化面板（Web UI）

本项目已内置 Web 管理面板（基于 FastAPI + SQLite），支持多账号管理、Cookie 配置、手动签到和日志查看。

**功能特性：**
1. **多账号管理**：支持添加/删除/启用/禁用账号。
2. **Cookie 免密**：支持配置 Cookie 跳过登录。
3. **实时日志**：Web 端查看运行状态。
4. **手动触发**：一键运行签到任务。

**数据持久化：**
- 数据文件：`./data/leaflow.db`
- 已通过 Docker Volume 挂载到宿主机 `./data` 目录。

---

## 💻 本地运行指南

如果你想在本地计算机上运行或调试脚本：

### 前置要求
- Python 3.8+
- Chrome 浏览器

### 步骤

1.  **克隆仓库**
    ```bash
    git clone https://github.com/your-username/leaflow-auto-checkin.git
    cd leaflow-auto-checkin
    ```

2.  **安装依赖**
    ```bash
    pip install -r requirements.txt
    ```

3.  **设置环境变量并运行**

    **Windows (PowerShell):**
    ```powershell
    $env:LEAFLOW_ACCOUNTS="email@example.com:password"
    python leaflow_checkin.py
    ```

    **Linux / macOS:**
    ```bash
    export LEAFLOW_ACCOUNTS="email@example.com:password"
    python leaflow_checkin.py
    ```

## 🔧 技术架构

- **核心**：基于 Selenium WebDriver 模拟真实用户行为。
- **环境适配**：
  - 自动识别 GitHub Actions 环境，使用 `headless=new` 模式。
  - 本地运行时可见浏览器窗口，方便调试。
  - 使用 `webdriver-manager` 自动管理 ChromeDriver 版本。
- **稳定性**：
  - 显式等待（Explicit Waits）确保元素加载。
  - 智能重试机制处理网络波动。
  - 详细的日志输出。

## ⚠️ 免责声明

- 本脚本仅用于学习和技术交流，请勿用于非法用途。
- 使用本脚本所造成的任何后果由使用者自行承担。
- 请勿滥用此脚本，以免对目标网站造成不必要的负担。


