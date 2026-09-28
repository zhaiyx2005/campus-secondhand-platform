import os


# 源码目录：同时也存放只读资源（templates / static）
SOURCE_DIR = os.path.abspath(os.path.dirname(__file__))
# 资源目录：打包成 exe 后指向解包目录，源码运行时就是源码目录
RESOURCE_DIR = os.environ.get("XHLY_RESOURCE_DIR", "").strip() or SOURCE_DIR
# 数据目录：数据库与上传文件所在位置，打包后跟随 exe 所在文件夹，保证数据不丢
BASE_DIR = os.environ.get("XHLY_DATA_DIR", "").strip() or SOURCE_DIR

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "").strip()
AI_API_KEY = os.environ.get("AI_API_KEY", "").strip()
USE_DEEPSEEK_DEFAULTS = bool(DEEPSEEK_API_KEY) and not AI_API_KEY


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "campus_second_hand.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif"}
    AI_ENABLED = os.environ.get("AI_ENABLED", "").strip().lower() == "true" or bool(AI_API_KEY or DEEPSEEK_API_KEY)
    AI_API_KEY = AI_API_KEY or DEEPSEEK_API_KEY
    AI_API_BASE_URL = os.environ.get(
        "AI_API_BASE_URL",
        "https://api.deepseek.com/chat/completions"
        if USE_DEEPSEEK_DEFAULTS
        else "https://api.openai.com/v1/chat/completions",
    )
    AI_MODEL = os.environ.get("AI_MODEL", "deepseek-chat" if USE_DEEPSEEK_DEFAULTS else "gpt-4o-mini")
    AI_REQUEST_TIMEOUT = int(os.environ.get("AI_REQUEST_TIMEOUT", "12"))
