# 旧物循用运行说明

这是一个本地运行版校园二手交易平台，后端使用 Flask，数据库使用 SQLite。

## 1. 安装 Python

电脑需要安装 Python 3.10 或以上版本。

安装后在命令行检查：

```powershell
python --version
```

如果 `python` 命令不可用，可以尝试：

```powershell
py --version
```

## 2. 解压项目

把压缩包解压到一个英文路径目录，例如：

```text
D:\second_hand_platform
```

## 3. 进入项目目录

```powershell
cd D:\second_hand_platform
```

如果你解压后的目录里面还有一层 `second_hand_platform_release_日期时间`，就进入那一层。

## 4. 创建虚拟环境

```powershell
python -m venv .venv
```

如果电脑使用的是 `py` 命令：

```powershell
py -m venv .venv
```

## 5. 激活虚拟环境

```powershell
.\.venv\Scripts\activate
```

激活成功后，命令行前面通常会出现 `(.venv)`。

## 6. 安装依赖

```powershell
pip install -r requirements.txt
```

## 7. 初始化数据库

```powershell
flask --app app init-db
```

## 8. 创建管理员账号

```powershell
flask --app app create-admin --account admin --password admin123456 --nickname 管理员
```

也可以把账号密码换成自己的。

## 9. 启动项目

如果要启用首页 AI 搜索，先在当前 PowerShell 窗口设置：

```powershell
$env:AI_ENABLED = "true"
$env:AI_API_KEY = "你的 API Key"
$env:AI_MODEL = "gpt-4o-mini"
$env:AI_API_BASE_URL = "https://api.openai.com/v1/chat/completions"
```

使用 DeepSeek 时可以简化为：

```powershell
$env:DEEPSEEK_API_KEY = "你的 DeepSeek API Key"
```

不设置这些环境变量也可以正常运行，系统会使用普通搜索。

```powershell
flask --app app run --host 127.0.0.1 --port 5000
```

看到类似下面内容说明启动成功：

```text
Running on http://127.0.0.1:5000
```

## 10. 打开网页

浏览器访问：

```text
http://127.0.0.1:5000
```

管理员后台：

```text
http://127.0.0.1:5000/admin
```

## 常见问题

如果提示 `flask` 不是命令，确认已经执行：

```powershell
.\.venv\Scripts\activate
pip install -r requirements.txt
```

如果端口被占用，可以换一个端口：

```powershell
flask --app app run --host 127.0.0.1 --port 5001
```

然后访问：

```text
http://127.0.0.1:5001
```

## 多用户与大数据量测试

进入 `final` 目录后，可以生成可重复的多用户、多类别商品数据：

```powershell
flask --app app seed-demo --users 20 --products-per-user 100
```

演示账号格式为 `demo_user_0001`，密码为 `demo123456`。需要重新生成时增加 `--reset`。首页和后台列表已经分页，默认不会一次性读取全部商品或用户。

SQLite 已启用 WAL 和忙等待；多人部署请配置 `DATABASE_URL` 指向 PostgreSQL/MySQL，并使用生产 WSGI 服务器。兑换接口在数据库事务内用条件更新处理并发点击，同一商品只会生成一个订单。

## AI 可用性检查

```powershell
Invoke-RestMethod "http://127.0.0.1:5000/health?ai=1"
flask --app app test-ai --query "想找 50 积分以内的考研数学教材"
```

返回的 `ai.available` 或命令输出代表真实接口探测结果。没有 AI Key 时会明确提示并自动使用本地关键词搜索。

## 功能入口

- 首页：商品列表、好友栏、AI帮你找
- 发布商品：上传图片、填写积分和标签
- 商品详情：收藏、积分兑换、添加卖家好友
- 个人中心：资料、头像、学号认证申请、积分增添申请、订单、收藏、好友管理
- 右下角消息：好友之间聊天
- 管理后台：用户、积分申请、学生认证、商品、订单管理

## 管理员操作说明

登录管理员账号后进入：

```text
http://127.0.0.1:5000/admin
```

常用后台入口：

- 用户管理：搜索用户、设置管理员、删除用户及其关联信息
- 积分管理：审核普通用户提交的积分增添申请
- 认证管理：审核普通用户提交的真实姓名和学号认证申请
- 商品管理：查看商品、修改商品状态
- 订单管理：查看平台交易记录

注意：普通用户在个人中心点击积分档位后，积分不会直接到账，需要管理员在 `积分管理` 里通过申请。
