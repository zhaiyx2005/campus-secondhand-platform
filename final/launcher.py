# -*- coding: utf-8 -*-
"""旧物循用 · 一键启动器

双击本程序（或打包好的「旧物循用.exe」）即可在本机启动网站，
并自动用默认浏览器打开首页。关闭这个黑色窗口就等于关闭网站。

也可以直接用 Python 运行：python launcher.py
"""
import ctypes
import logging
import os
import shutil
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

try:
    import db_seed
except Exception:  # noqa: BLE001
    db_seed = None

APP_TITLE = "旧物循用 · 校园二手交易平台"
HOST = "127.0.0.1"
PREFERRED_PORT = 5000
MAX_PORT_TRIES = 20
DB_NAME = "campus_second_hand.db"
HOME_MARKER = "旧物循用"


# --------------------------------------------------------------------------- #
# 路径
# --------------------------------------------------------------------------- #
def is_frozen():
    """是否运行在 PyInstaller 打包出的 exe 里。"""
    return bool(getattr(sys, "frozen", False))


def app_dir():
    """可写目录：打包后是 exe 所在文件夹，源码运行时是源码文件夹。"""
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def resource_dir():
    """只读资源目录（templates / static）。"""
    if is_frozen():
        return getattr(sys, "_MEIPASS", app_dir())
    return os.path.dirname(os.path.abspath(__file__))


def prepare_environment():
    """确定数据目录、补齐数据库与上传目录，并把结果传给 config.py。"""
    base = app_dir()
    res = resource_dir()
    os.environ["XHLY_DATA_DIR"] = base
    os.environ["XHLY_RESOURCE_DIR"] = res

    os.makedirs(os.path.join(base, "uploads", "avatars"), exist_ok=True)

    db_path = os.path.join(base, DB_NAME)
    if not os.path.exists(db_path):
        # 优先从打包进 exe 的二进制种子写入（避免只读资源目录权限问题）
        if db_seed is not None and getattr(db_seed, "DATA", None):
            with open(db_path, "wb") as fh:
                fh.write(db_seed.DATA)
        else:
            seed = os.path.join(res, DB_NAME)
            if os.path.exists(seed):
                shutil.copy2(seed, db_path)
    return base, db_path


# --------------------------------------------------------------------------- #
# 端口探测
# --------------------------------------------------------------------------- #
def port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((HOST, port))
        except OSError:
            return False
    return True


def looks_like_our_site(port, timeout=2.0):
    """端口已被占用时，判断那是不是本程序之前启动的网站。"""
    try:
        with urllib.request.urlopen("http://%s:%d/" % (HOST, port), timeout=timeout) as resp:
            html = resp.read(8192).decode("utf-8", "replace")
        return HOME_MARKER in html
    except (urllib.error.URLError, OSError, ValueError):
        return False


def find_running_instance():
    for port in range(PREFERRED_PORT, PREFERRED_PORT + MAX_PORT_TRIES):
        if not port_free(port) and looks_like_our_site(port):
            return port
    return None


def find_free_port():
    for port in range(PREFERRED_PORT, PREFERRED_PORT + MAX_PORT_TRIES):
        if port_free(port):
            return port
    raise RuntimeError("端口 %d~%d 都被占用了，请先关掉占用端口的程序。"
                       % (PREFERRED_PORT, PREFERRED_PORT + MAX_PORT_TRIES - 1))


# --------------------------------------------------------------------------- #
# 界面
# --------------------------------------------------------------------------- #
def enable_console_features():
    try:
        ctypes.windll.kernel32.SetConsoleTitleW(APP_TITLE)
    except Exception:  # noqa: BLE001
        pass
    try:
        handle = ctypes.windll.kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        if ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            ctypes.windll.kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:  # noqa: BLE001
        pass


def banner(port, db_path, first_run):
    url = "http://%s:%d/" % (HOST, port)
    lines = [
        "",
        "  ============================================================",
        "        旧 物 循 用  ·  校园二手交易平台  本地服务",
        "  ============================================================",
        "",
        "    网  址   %s" % url,
        "    管理后台  %sadmin" % url,
        "",
        "    数据库    %s" % db_path,
        "    上传目录  %s" % os.path.join(app_dir(), "uploads"),
        "",
    ]
    if first_run:
        lines += [
            "    首次运行：已自动准备好数据库，可直接注册新账号使用。",
            "    管理员账号可在项目目录用 create-admin 命令创建。",
            "",
        ]
    lines += [
        "    浏览器没有自动打开？把上面的网址复制到浏览器打开即可。",
        "",
        "    ★ 保持本窗口开着，网站才会一直运行。",
        "    ★ 关闭本窗口（或按 Ctrl+C）即停止网站。",
        "",
    ]
    print("\n".join(lines), flush=True)


def open_browser_when_ready(port, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(0.25)
        if not port_free(port):
            break
    try:
        webbrowser.open("http://%s:%d/" % (HOST, port))
    except Exception:  # noqa: BLE001
        pass


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def main():
    enable_console_features()
    db_before = os.path.join(app_dir(), DB_NAME)
    first_run = not os.path.exists(db_before) or os.path.getsize(db_before) == 0
    base, db_path = prepare_environment()

    running = find_running_instance()
    if running:
        print("\n  检测到网站已经在运行，正在打开浏览器……", flush=True)
        webbrowser.open("http://%s:%d/" % (HOST, running))
        time.sleep(1.5)
        return 0

    port = find_free_port()

    # 必须在导入 app 之前设置好 XHLY_DATA_DIR / XHLY_RESOURCE_DIR
    import app as webapp  # noqa: PLC0415

    banner(port, db_path, first_run)
    threading.Thread(target=open_browser_when_ready, args=(port,), daemon=True).start()

    try:
        # 隐藏 Flask/Werkzeug 的 development server 警告，保留我们窗口里的简洁输出
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        webapp.app.run(
            host=HOST,
            port=port,
            debug=False,
            use_reloader=False,
            threaded=True,
        )
    except KeyboardInterrupt:
        print("\n  网站已停止。\n", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
