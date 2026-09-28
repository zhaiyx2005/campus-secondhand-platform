# 旧物循用

校园二手交易平台第一阶段功能：用户注册登录、商品发布、商品列表展示、个人中心展示。

## 技术栈

- 后端：Python Flask
- 数据库：SQLite + SQLAlchemy ORM
- 前端：HTML + CSS + JavaScript + Bootstrap
- 模板引擎：Jinja2
- 登录状态：Flask session
- 图片上传：本地 `uploads/` 文件夹

## 功能说明

- 未登录访问首页会自动跳转到登录页。
- 登录成功后进入主功能页，布局包括顶部导航、好友栏、商品列表、AI帮你找。
- 商品发布使用积分，不使用现金价格。
- 商品标签由卖家自由填写，支持多个标签，例如 `#衣服 #连衣裙 #毕业闲置`。
- 个人中心支持上传头像、修改资料、修改密码、姓名与学号认证申请、积分增添申请、积分明细和我的发布状态管理。
- 登录使用用户名和密码；忘记密码可通过用户名和个人中心预留手机号/联系方式重置。
- 好友之间支持右下角悬浮聊天窗发送站内消息。
- 管理员后台支持平台概览、用户管理、商品管理和订单管理。
- 管理员后台支持积分申请审核、学生认证审核、删除用户及其关联出售/购买信息。
- 我的订单、我的收藏、好友管理目前保留入口和展示位，便于后续阶段接入。

## 安装依赖

```bash
cd second_hand_platform
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 初始化数据库

```bash
flask init-db
```

执行后会生成 `campus_second_hand.db` SQLite 数据库文件。

## 启动项目

```bash
python app.py
```

浏览器访问：

```text
http://127.0.0.1:5000
```

## 管理员后台

本地已创建默认管理员账号：

```text
账号：admin
密码：admin123456
```

登录后访问：

```text
http://127.0.0.1:5000/admin
```

也可以手动创建或重置管理员账号：

```bash
flask --app app create-admin --account admin --password admin123456 --nickname 管理员
```

后台功能：

- `/admin`：平台概览
- `/admin/users`：用户搜索、认证状态、管理员权限、删除用户
- `/admin/points`：积分增添申请审核
- `/admin/verifications`：学生认证申请审核
- `/admin/products`：商品搜索、状态筛选、状态调整
- `/admin/orders`：订单查询和积分交易记录

## 主要路由

- `GET /`：登录后的主功能页/商品列表页
- `GET /register`：注册页
- `POST /register`：处理注册
- `GET /login`：登录页
- `POST /login`：处理登录
- `GET /forgot-password`：忘记密码页
- `POST /forgot-password`：通过预留联系方式重置密码
- `GET /logout`：退出登录
- `GET /profile`：个人中心页
- `POST /profile/avatar`：上传头像
- `POST /profile/update-info`：修改昵称、联系方式、学校、个人标签
- `POST /profile/change-password`：修改密码
- `POST /profile/verify-student`：提交姓名和学号认证申请
- `POST /profile/recharge`：积分充值
- `POST /profile/product/<id>/status`：修改本人发布商品的状态
- `POST /chat/send/<friend_id>`：给好友发送站内消息
- `GET /admin`：管理员后台概览
- `GET /admin/users`：后台用户管理
- `POST /admin/users/<id>/toggle-admin`：切换管理员权限
- `POST /admin/users/<id>/toggle-verified`：切换用户认证状态
- `POST /admin/users/<id>/points`：后台调整用户积分
- `POST /admin/users/<id>/delete`：删除用户及其关联出售、购买、好友、聊天等信息
- `GET /admin/points`：后台积分申请管理
- `POST /admin/points/<id>/review`：审核积分申请
- `GET /admin/verifications`：后台学生认证申请管理
- `POST /admin/verifications/<id>/review`：审核学生认证申请
- `GET /admin/products`：后台商品管理
- `POST /admin/products/<id>/status`：后台调整商品状态
- `GET /admin/orders`：后台订单管理
- `GET /publish`：商品发布页
- `POST /publish`：处理商品发布
- `GET /uploads/<filename>`：访问上传图片

## AI 搜索配置

首页搜索框已经支持“自然语言描述需求”。未开启 AI 时会自动回退到原来的标题、描述、标签关键词搜索。

开启 AI 搜索前设置环境变量：

```powershell
$env:AI_ENABLED = "true"
$env:AI_API_KEY = "你的 API Key"
$env:AI_MODEL = "gpt-4o-mini"
$env:AI_API_BASE_URL = "https://api.openai.com/v1/chat/completions"
```

兼容 OpenAI Chat Completions 格式的服务可以替换 `AI_API_BASE_URL` 和 `AI_MODEL`。

如果使用 DeepSeek，可以直接设置：

```powershell
$env:DEEPSEEK_API_KEY = "你的 DeepSeek API Key"
```

系统会默认使用：

```text
AI_API_BASE_URL=https://api.deepseek.com/chat/completions
AI_MODEL=deepseek-chat
```

也可以通过 `AI_API_BASE_URL` 和 `AI_MODEL` 覆盖默认值。

## 数据表

- `user`：账号、密码、昵称、头像、学校、联系方式、积分余额、信用分、个人标签、创建/更新时间。
- `product`：发布用户、标题、描述、所需积分、标签、状态、浏览次数、创建/更新时间。
- `product_image`：商品图片路径、排序、创建时间。
- `point_record`：积分变动记录、变动后余额、类型、说明、创建时间。

## 测试流程

1. 访问 `/`，确认会自动跳转到 `/login`。
2. 访问 `/register`，注册一个用户。
3. 访问 `/login`，使用刚注册的账号登录。
4. 可勾选“记住密码”，下次打开登录页会自动填充账号和密码。
5. 登录成功后进入主功能页，查看好友栏、商品列表、AI帮你找和顶部导航。
6. 进入 `/publish`。
7. 填写商品标题、描述、所需积分、商品标签。
8. 标签可填写多个，例如 `#衣服 #连衣裙`，也可以写 `衣服 连衣裙`，系统会自动补 `#`。
9. 上传 1 到 6 张 `jpg/jpeg/png/gif` 图片。
10. 点击发布商品。
11. 发布成功后自动回到首页。
12. 首页商品卡片显示首图、标题、积分、标签、发布时间、发布者昵称。
13. 点击个人中心，查看用户信息和积分卡片。
14. 在个人中心测试上传头像、修改资料、学号认证、积分充值、查看积分明细。
15. 在“我的发布列表”修改商品状态，例如从“在售”改为“已下架”。
16. 点击退出登录，返回登录页。

## 校验说明

- 注册时校验账号、昵称、密码、确认密码、密码长度和账号唯一性。
- 登录时校验用户名是否存在和密码是否正确。
- 忘记密码时校验用户名、预留手机号/联系方式、新密码和确认密码。
- 未登录访问 `/`、`/publish`、`/profile` 会自动跳转到 `/login`。
- 发布商品时校验标题、描述、积分、标签、图片数量和图片格式。
- 密码使用 `werkzeug.security` 加密后保存，数据库不保存明文密码。
