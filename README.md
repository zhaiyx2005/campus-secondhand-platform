# 旧物循用 · 校园二手交易平台

基于 Flask + SQLAlchemy 的校园闲置物品交易平台，以**积分**作为交易媒介，并集成大模型实现自然语言商品检索。

## 下载即玩（免安装）

不想配 Python 环境？直接下载打包好的 Windows 免安装版：

- **Gitee Releases（国内推荐，秒开）**：https://gitee.com/zhaiyx2005/campus-secondhand-platform/releases/tag/v1.1 （约 16 MB）
- **GitHub**：https://github.com/zhaiyx2005/campus-secondhand-platform —— 代码镜像。
  （GitHub 的附件下载域名在国内网络下不可达，免安装包请从上方 Gitee 下载）

解压后双击 `旧物循用.exe`，程序会自动启动本地服务并打开浏览器（http://127.0.0.1:5000/）。
首次运行会在同目录生成数据库与上传目录，关闭命令行窗口即停止服务。

> 从源码运行的方式见 [README-一键启动.md](README-一键启动.md)。

## 技术栈

| 层次 | 技术 |
| --- | --- |
| Web 框架 | Flask 3.0 |
| ORM | Flask-SQLAlchemy 3.1 |
| 数据库 | SQLite |
| 模板引擎 | Jinja2 |
| 前端 | HTML / CSS / JavaScript / Bootstrap |
| 大模型 | DeepSeek Chat Completions API |
| 打包 | PyInstaller |

## 数据规模

- **12 张数据表**
- **37 个路由**
- **15 个页面模板**
- 约 2200 行 Python 代码

## 核心功能

### 交易闭环

商品发布（支持最多 6 张图）、积分结算、收藏与浏览记录、订单与积分流水。

买家扣分、卖家入账、订单落库与双方积分流水在**同一数据库事务内**完成，异常时回滚并清理已落盘图片，避免出现「扣了分却没订单」的脏数据。

### AI 自然语言检索

将「想吃的东西」这类模糊需求交给 DeepSeek，解析为结构化 JSON（关键词、标签、积分区间），再叠加同义词扩展与加权相关度排序：

```
标签命中 > 标题命中 > 描述命中，并计入浏览热度与发布时间衰减
```

AI 接口超时或未配置密钥时，自动降级为本地关键词扩展召回与规则标签生成，保证核心链路不中断。

### 管理员后台

用户管理、商品管理、订单查询、积分审核、学生认证审核、数据概览六大模块。基于装饰器实现登录态与管理员两级权限控制。

## 目录结构

```
final/
  app.py                应用入口、路由与业务控制
  models.py             12 张数据表定义
  config.py             配置
  services/
    ai_client.py        DeepSeek 调用、意图解析、标签生成
    product_search.py   关键词扩展与相关度排序
  templates/            Jinja2 页面模板（含 admin 后台）
  static/               CSS / JS / 图片
_build/                 打包工具链（不入版本库）
```

## 运行方式

```bash
cd final
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
flask init-db
python app.py
```

访问 `http://127.0.0.1:5000`

### AI 检索配置（可选）

```powershell
$env:DEEPSEEK_API_KEY = "你的 API Key"
$env:AI_ENABLED = "true"
```

不配置也能正常使用，系统会自动走本地关键词检索。

### 管理员后台

| 项目 | 值 |
| --- | --- |
| 地址 | `http://127.0.0.1:5000/admin` |
| 默认账号 | 由 `flask create-admin` 命令生成 |

## 扩展、并发与测试

当前版本已为增长场景做了基础升级：目录和后台列表分页，商品搜索限制 AI 候选集并使用数据库索引；SQLite 默认开启 WAL、外键和忙等待，多用户兑换通过条件更新保证同一商品只成交一次。多人部署时设置 `DATABASE_URL` 接入 PostgreSQL/MySQL，并用生产 WSGI 服务器运行。

进入 `final` 后可以生成多组可重复演示数据：

```powershell
flask --app app seed-demo --users 20 --products-per-user 100
```

检查数据库和 AI 配置：

```powershell
Invoke-RestMethod http://127.0.0.1:5000/health
Invoke-RestMethod "http://127.0.0.1:5000/health?ai=1"
flask --app app test-ai
```

没有配置 AI Key 时，AI 检索会自动回退到本地关键词和同义词搜索；`test-ai` 只有在配置 Key 后才会发起真实接口探测。开发依赖和无网络回归测试位于 `final/requirements-dev.txt` 与 `final/tests/`。

## 更新日志

### v1.1 —— 工程质量升级

- **兑换并发安全**：`TradeOrder.product_id` 增加唯一约束，余额校验与扣减放在同一事务内，
  配合条件更新与回滚，保证同一商品在并发兑换下只会成交一次
- **后台分页**：用户 / 充值申请 / 学生认证三个列表改为分页（每页 50 条）
- **数据库索引**：新增 8 组复合索引（商品 `status + create_time`、积分记录 `user_id + create_time`、
  聊天 `receiver_id + is_read + create_time` 等）
- **连接与部署**：SQLite 开启 WAL、外键约束与忙等待；支持 `DATABASE_URL` 切换到 PostgreSQL / MySQL
- **Cookie 安全**：`HttpOnly` + `SameSite=Lax`，`Secure` 开关可由环境变量控制
- **图片安全**：新增 `product_image_url` 过滤器，做路径穿越校验，缺失图片回退占位图
- **AI 检索**：限制候选集规模；未配置 Key 时自动回退本地关键词与同义词搜索
- **可观测与运维**：新增 `/health` 健康检查、`seed-demo` 演示数据、`test-ai` 配置探测三个入口
- **测试**：新增 `final/tests/`（pytest）与 `final/requirements-dev.txt`，3 项回归全部通过

### v1.0 —— 首个可玩版本

完整交易闭环（发布 / 检索 / 下单 / 积分结算）、AI 自然语言检索、管理员后台。

## 备注

个人学习与作品集项目。运行所需的示例图片与数据库文件不入库，首次运行会自动建库。
