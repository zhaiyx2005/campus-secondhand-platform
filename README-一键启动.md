# 旧物循用 · 一键启动

## 1. 双击运行

把 `旧物循用.exe` 放到你喜欢的文件夹，然后**双击**即可：

- 自动启动本地网站服务
- 自动用默认浏览器打开 http://127.0.0.1:5000/
- 关闭黑色窗口即停止服务

> 首次运行会在 `旧物循用.exe` 所在目录生成 `campus_second_hand.db` 和 `uploads/` 文件夹，这是正常的数据和上传文件目录。

## 2. 数据说明

- `campus_second_hand.db`：SQLite 数据库，记录用户、商品、订单、好友等数据。
- `uploads/`：用户上传的商品图片、头像等。
- 把这两个文件/文件夹一起复制到新位置，就相当于把整站数据一起搬走。

## 3. 管理员账号

`旧物循用.exe` 不带管理员创建界面。需要管理员账号时，请在 `final/` 目录执行：

```powershell
.\.venv\Scripts\activate
flask --app app create-admin --account admin --password admin123456 --nickname 管理员
```

## 4. 源码方式启动

如果你想从源码运行，进入 `final/` 目录：

```powershell
.\.venv\Scripts\activate
python launcher.py
```

（`.venv` 中的依赖已重新安装好。）

## 5. 常见问题

**Q：提示端口 5000 被占用？**
A：程序会自动尝试 5000~5019 之间的端口。如果一直被占用，请关闭占用端口的程序再试。

**Q：浏览器没自动打开？**
A：手动访问窗口里打印的网址（例如 http://127.0.0.1:5000/）。

**Q：杀毒软件提示风险？**
A：这是 PyInstaller 打包的单文件 exe，可能会被个别杀毒软件误报。如不放心，可用源码方式启动。
