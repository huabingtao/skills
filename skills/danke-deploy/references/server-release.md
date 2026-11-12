# 服务器发布流程

## 环境和状态

每次从活动PM2进程重新确认路径。历史首次目录为/var/www/danke-core；2026-11-06联合版本位于/var/www/danke-releases/joint-20261106-v1/core，活动库位于同批data/danke.sqlite。这是发现线索，不是永久固定目录。先确认再使用。

创建唯一批次目录 /var/www/danke-releases/<release>/ 和私有备份目录 /var/backups/danke-joint-<release>/。备份目录权限700，含环境或PM2环境的文件权限600。SSH凭证只用于本次连接，使用临时ControlMaster可以避免重复输入，不保存密码。

## 数据与图片

- 从当前活动库使用SQLite backup API做一致性快照，不直接复制运行中的WAL文件。
- 备份当前Web、Core代码/运行配置、Nginx配置和共享uploads；PM2环境快照仅存服务器私有目录。
- 以CLI生成的game-data.sqlite为游戏资料基线。复制线上User、Role、Permission、_RolePermissions、Menu、GameEvent、ReminderRule、UserViewPreference（仅复制线上存在的表）。不复制本地账号。不导入StrategyArticle历史内容。
- 新表默认空。存在CLI白名单以外的线上业务表时，先保留到新库，若Schema不兼容则停止并报告具体表，不默默丢弃。
- 图片从game-data.json清单同步至共享uploads，保留旧文件。同路径内容相同则复用；内容不同则用内容哈希后缀另存，并只更新暂存游戏数据中的对应URL，不能覆盖旧图。
- 分类图片不在数据库icon字段内，必须连同清单收集。Core public/uploads在启动前链接共享目录，不另建一套独立图片目录。
- 执行integrity_check和foreign_key_check，核对游戏表数量及线上账号/密码哈希/角色/权限记录保持一致。这是数据切换必需检查，不属于逐页验收。

## 暂存和构建

服务器按锁文件npm ci、prisma generate、npm run build；原生SQLite模块在服务器编译。只用Core专用Node24，不升级全局Node或依赖版本。

私有环境文件保留现有ADMIN_API_KEY和JWT_SECRET。若缺JWT_SECRET，首次生成随机值并持久保存，之后复用；不生成本地账号。Core生产CORS仅允许Web/Admin HTTPS来源，HOST=127.0.0.1，正式PORT=3003，暂存PORT选择空闲回环端口33103。

通过SSH隧道让本地生产构建读取暂存Core，或在服务器构建。浏览器地址仍是正式HTTPS Core，不能烘焙隧道或localhost地址。旧/strategies入口跳到/guides，已确认旧URL逐条精确映射；不生成测试夹具，不按标题猜测大量301。

## 切换及结束

> **注**：对于日常仅涉及攻略文章与 Web 静态页面的增量更新，可直接使用根目录一键脚本 `python3 scripts/deploy_web_articles.py`，该脚本已完全封装并自动化执行下述第 1~5 步中的备份、硬链接复用、原子软链切换及 Nginx 重载流程。

1. 暂存产物校验完成后，Core公网写请求短暂维护；停止旧Core，补做最终SQLite备份并重新复制线上受保护记录，避免丢失准备期间的账号变更。
2. 启动新Core为PM2 danke-core、端口3003、专用Node24。保留其他应用PID和配置。
3. 通过新临时链接与os.replace切换Web公开out，保留旧目录和可执行回滚步骤。Nginx只修改Web/Core对应块，保留HTTPS与uploads。
4. Nginx干净URL先匹配实际.html；带尾斜杠路径先内部规范化。Next导出目录还包含RSC文本资源，不能将这些请求回退成首页HTML。未知地址返回404。
5. 执行Nginx -t后reload。只在用户要求时做浏览器/逐页验收；否则必要启动检查完成就解除临时写入维护，交给用户验收，不能无限保持503。
6. 删除本次暂存PM2进程并pm2 save；不删除旧版本或备份。不让凭证进入CLI输出或本地报告。

启动或切换失败时恢复旧Core进程参数、旧数据库/公开根和Nginx配置；保持受保护数据不丢失。解除写入维护后的回滚先评估新增写入，不能直接用旧库覆盖新数据。

## 范围提醒

此前完整部署自动验收曾中断，不能据历史话术宣称所有浏览器流程已通过。每次如实记录执行范围。仅修复静态图片时同步共享文件即可，不要求重新构建整个Web，也不要自动运行用户明确拒绝的页面验证。
