---
name: danke-deploy
description: 打包和部署 danke-web、danke-admin、danke-core 到生产服务器（国内腾讯云 124.220.195.160 与海外 195.72.191.81）。当用户说“发布弹壳网站”、“打包上线”、“部署Web/Core/Admin”、“更新服务器”、“发布新攻略到网站”或“单独部署”时触发。支持【单项目独立解耦部署 (web/admin/core)】与【全栈联合发布】双模式；包含独立环境配置、游戏数据白名单、静态大图硬链接复用、原子软链切换及回滚；凭证不落盘。默认不跑浏览器或逐页验收，由用户自行验证，只有明确要求才启用。
---

# Danke 网站与服务部署指南

先读取工作区和当前项目 AGENTS.md。使用真实 WSL 路径、Node24。用户要求打包就只打包，要求部署才上传及切换；本技能不授权提交 Git、发送消息或发布微信公众号。

## 一、 服务器节点与域名架构

### 1. 国内节点（腾讯云）
- **主机 IP**：`124.220.195.160`
- **Web 门户**：`https://dankeweb.guaguahub.cn`（目录 `/var/www/danke-web/out`）
- **Admin 看板**：`https://dankeadmin.guaguahub.cn`（目录 `/var/www/danke-admin/out`）
- **Core 中枢**：`https://dankecore.guaguahub.cn`（目录 `/var/www/danke-releases/joint-*/core`，PM2 `danke-core`，端口 3003）

### 2. 海外节点
- **主机 IP**：`195.72.191.81`
- **凭证存储**：`~/.config/danke-deploy/overseas_server.json`（禁止将凭证提交至仓库）
- **Web 门户**：`https://danke.guaguayun.top`（目录 `/var/www/danke-web/out`）
- **Admin 看板**：`https://admin.guaguayun.top`（目录 `/var/www/danke-admin/out`）
- **Core 中枢**：`https://core.guaguayun.top`（目录 `/var/www/danke-core/dist`，PM2 `danke-core`，端口 3003）

---

## 二、 核心部署模式

### 模式 A：【单项目独立解耦部署】（推荐日常高频使用 ⭐）
为了避免任意单一模块变动牵连整站或重启后端，部署脚本已完全解耦为独立模块控制：

```bash
# 1. 独立部署 danke-web（静态玩家门户，不触碰后端与数据库，仅切流并重载 Nginx，秒级完成）
python3 scripts/deploy_services_to_overseas.py --target web
# 若需要在部署前自动在本地执行生产构建 (npm run build:prod)，附加 --build：
python3 scripts/deploy_services_to_overseas.py --web --build

# 2. 独立部署 danke-admin（管理后台看板）
python3 scripts/deploy_services_to_overseas.py --target admin
# 自动构建并部署：
python3 scripts/deploy_services_to_overseas.py --admin --build

# 3. 独立部署 danke-core（后端业务中枢与规则引擎，自动远端备份数据库并安全重启 PM2）
python3 scripts/deploy_services_to_overseas.py --target core
# 自动构建并部署：
python3 scripts/deploy_services_to_overseas.py --core --build
```

### 模式 B：【全量联合发布】
当全栈联动更新（如同时包含数据表变更、API 迭代与前端看板升级）时：
```bash
python3 scripts/deploy_services_to_overseas.py --target all --build
```

### 模式 C：【国内生产节点日常攻略切流】
针对国内腾讯云节点的攻略文章与增量 Web 产物部署：
```bash
# 1. 打包
python3 .agents/skills/danke-deploy/scripts/deploy_bundle.py web-bundle --web-out project/danke/danke-web/out
# 2. 一键远程切流
python3 scripts/deploy_web_articles.py
```

---

## 三、 常用 CLI 速查表

| 场景 / 目标 | 命令 | 说明 |
| :--- | :--- | :--- |
| **海外独立部署 Web** | `python3 scripts/deploy_services_to_overseas.py --web [--build]` | 仅部署 `danke-web`，秒级原子切流 |
| **海外独立部署 Admin** | `python3 scripts/deploy_services_to_overseas.py --admin [--build]` | 仅部署 `danke-admin`，原子切流 |
| **海外独立部署 Core** | `python3 scripts/deploy_services_to_overseas.py --core [--build]` | 仅部署 `danke-core`，含数据库备份与 PM2 重启 |
| **海外全量部署** | `python3 scripts/deploy_services_to_overseas.py --all [--build]` | 全栈三个模块顺序部署与全链路健康探针 |
| **国内增量攻略切流** | `python3 scripts/deploy_web_articles.py` | 国内节点秒级切流 |
| **国内全量联合部署** | `python3 scripts/deploy_production.py` | 国内节点全量发布 |

---

## 四、 规范与铁律
1. **凭证不落盘**：绝不向代码库、Git 提交或日志输出明文密码与密钥。
2. **防泄漏门禁**：所有前端静态产物在打包上传前，必须执行 `check_artifact_for_leaks` 扫描，绝不允许残留 `localhost:610*` 等本地调试地址。
3. **原子切流保活**：必须采用 `out_new` 解压后再 `mv` 或软链原子切换，杜绝出现 404 窗口期。
4. **耗时留痕**：部署完成后必须按阶段输出耗时明细表。
