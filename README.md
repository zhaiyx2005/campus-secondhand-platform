# 旧物循用 · 校园二手交易平台

基于 Flask + SQLAlchemy 的校园闲置物品交易平台，以**积分**作为交易媒介，并集成大模型实现自然语言商品检索。

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

## 备注

个人学习与作品集项目。运行所需的示例图片与数据库文件不入库，首次运行会自动建库。
