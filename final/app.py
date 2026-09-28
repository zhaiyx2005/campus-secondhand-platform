import os
import re
import uuid
from datetime import datetime
from functools import wraps

import click
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from sqlalchemy import or_, text
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from config import Config, RESOURCE_DIR
from models import (
    BrowseHistory,
    ChatMessage,
    Favorite,
    FriendRequest,
    Friendship,
    PointRecord,
    PointRechargeRequest,
    Product,
    ProductImage,
    StudentVerificationRequest,
    TradeOrder,
    User,
    db,
)
from services.ai_client import generate_product_tags, parse_product_search_intent
from services.product_search import search_products


RECHARGE_PLANS = {
    "10": 100,
    "50": 600,
    "100": 1300,
}
PRODUCT_STATUS_OPTIONS = ("在售", "已售出", "已下架")
PRODUCT_STATUSES = set(PRODUCT_STATUS_OPTIONS)
ORDER_STATUS_COMPLETED = "已完成"
FRIEND_REQUEST_PENDING = "待处理"
FRIEND_REQUEST_ACCEPTED = "已同意"
FRIEND_REQUEST_REJECTED = "已拒绝"
REQUEST_PENDING = "待审核"
REQUEST_APPROVED = "已通过"
REQUEST_REJECTED = "已拒绝"


def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(RESOURCE_DIR, "templates"),
        static_folder=os.path.join(RESOURCE_DIR, "static"),
    )
    app.config.from_object(Config)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], "avatars"), exist_ok=True)
    db.init_app(app)

    with app.app_context():
        ensure_database_schema()

    register_routes(app)
    register_commands(app)
    return app


def ensure_database_schema():
    db.create_all()
    user_columns = {row[1] for row in db.session.execute(text("PRAGMA table_info(user)")).fetchall()}
    user_additions = {
        "real_name": "ALTER TABLE user ADD COLUMN real_name VARCHAR(80)",
        "student_id": "ALTER TABLE user ADD COLUMN student_id VARCHAR(60)",
        "shipping_address": "ALTER TABLE user ADD COLUMN shipping_address VARCHAR(255)",
        "is_verified": "ALTER TABLE user ADD COLUMN is_verified BOOLEAN NOT NULL DEFAULT 0",
        "is_admin": "ALTER TABLE user ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0",
        "points_balance": "ALTER TABLE user ADD COLUMN points_balance INTEGER NOT NULL DEFAULT 250",
        "credit_score": "ALTER TABLE user ADD COLUMN credit_score INTEGER NOT NULL DEFAULT 98",
        "personal_tags": "ALTER TABLE user ADD COLUMN personal_tags VARCHAR(255)",
    }
    for column, ddl in user_additions.items():
        if column not in user_columns:
            db.session.execute(text(ddl))

    product_columns = {row[1] for row in db.session.execute(text("PRAGMA table_info(product)")).fetchall()}
    product_additions = {
        "points": "ALTER TABLE product ADD COLUMN points INTEGER NOT NULL DEFAULT 1",
        "tags": "ALTER TABLE product ADD COLUMN tags VARCHAR(255) NOT NULL DEFAULT '#其他'",
        "view_count": "ALTER TABLE product ADD COLUMN view_count INTEGER NOT NULL DEFAULT 0",
    }
    for column, ddl in product_additions.items():
        if column not in product_columns:
            db.session.execute(text(ddl))

    db.session.commit()


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            flash("请先登录后再进入旧物循用平台。", "warning")
            return redirect(url_for("login", next=request.path))
        if db.session.get(User, user_id) is None:
            session.clear()
            flash("登录状态已失效，请重新登录。", "warning")
            return redirect(url_for("login", next=request.path))
        return view_func(*args, **kwargs)

    return wrapper


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            flash("请先使用管理员账号登录。", "warning")
            return redirect(url_for("login", next=request.path))

        user = db.session.get(User, user_id)
        if user is None:
            session.clear()
            flash("登录状态已失效，请重新登录。", "warning")
            return redirect(url_for("login", next=request.path))
        if not user.is_admin:
            flash("当前账号没有管理员权限。", "danger")
            return redirect(url_for("index"))
        return view_func(*args, **kwargs)

    return wrapper


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


def allowed_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in Config.ALLOWED_IMAGE_EXTENSIONS


def save_uploaded_image(file_storage, subfolder=""):
    original_name = secure_filename(file_storage.filename)
    extension = original_name.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{extension}"
    upload_dir = os.path.join(Config.UPLOAD_FOLDER, subfolder)
    os.makedirs(upload_dir, exist_ok=True)
    save_path = os.path.join(upload_dir, filename)
    file_storage.save(save_path)
    url_path = "/".join(part for part in ["uploads", subfolder, filename] if part)
    return filename, f"/{url_path}"


def save_product_image(file_storage):
    return save_uploaded_image(file_storage)


def normalize_tags(raw_tags):
    tags = []
    for item in raw_tags.replace("，", " ").replace(",", " ").split():
        tag = item.strip()
        if not tag:
            continue
        if not tag.startswith("#"):
            tag = f"#{tag}"
        if tag not in tags:
            tags.append(tag)
    return tags


def validate_register_form(account, nickname, password, confirm_password):
    if not account:
        return "用户名不能为空"
    if not nickname:
        return "昵称不能为空"
    if not password:
        return "密码不能为空"
    if len(password) < 6:
        return "密码长度不能少于 6 位"
    if password != confirm_password:
        return "两次密码不一致"
    if User.query.filter_by(account=account).first():
        return "用户名已存在"
    return ""


def validate_password_reset_form(account, contact, password, confirm_password):
    if not account:
        return "用户名不能为空", None
    if not contact:
        return "请输入预留手机号或联系方式", None
    if not password:
        return "新密码不能为空", None
    if len(password) < 6:
        return "新密码长度不能少于 6 位", None
    if password != confirm_password:
        return "两次密码不一致", None

    user = User.query.filter_by(account=account).first()
    if not user:
        return "用户名不存在", None
    if not user.contact:
        return "该账号还没有完善手机号/联系方式，暂时无法自助找回密码，请联系管理员。", None
    if user.contact.strip() != contact.strip():
        return "预留手机号或联系方式不匹配", None
    return "", user


def validate_product_form(title, description, points_text, raw_tags, image_files):
    if not title:
        return "商品标题不能为空", None, []
    if not description:
        return "商品描述不能为空", None, []
    try:
        points = int(points_text)
    except (TypeError, ValueError):
        return "商品积分必须是整数", None, []
    if points <= 0:
        return "商品积分必须大于 0", None, []
    tags = normalize_tags(raw_tags)
    if not tags:
        return "商品标签不能为空", None, []
    if len(tags) > 8:
        return "商品标签最多填写 8 个", None, []
    if any(len(tag) > 20 for tag in tags):
        return "单个标签长度不能超过 20 个字符", None, []
    if len(image_files) < 1 or len(image_files) > 6:
        return "商品图片数量必须为 1 到 6 张", None, []
    for image_file in image_files:
        if not allowed_image(image_file.filename):
            return "只允许上传 jpg、jpeg、png、gif 格式图片", None, []
    return "", points, tags


def fallback_product_tags(title, description):
    text = f"{title} {description}".lower()
    rules = [
        ("#教材", ("教材", "课本", "高数", "数学", "英语", "考研", "复习", "资料", "书")),
        ("#数码", ("电脑", "键盘", "鼠标", "耳机", "手机", "充电", "数据线", "平板")),
        ("#生活用品", ("杯子", "台灯", "收纳", "床帘", "衣架", "日用")),
        ("#衣物", ("衣服", "外套", "裙", "裤", "鞋", "帽")),
        ("#食品", ("吃", "食品", "食物", "零食", "水果", "饮料", "茄子")),
        ("#运动", ("篮球", "足球", "球拍", "跑步", "健身", "运动")),
        ("#毕业闲置", ("毕业", "闲置", "转让")),
        ("#九成新", ("九成新", "很新", "保存很好", "几乎没用")),
    ]
    tags = []
    for tag, keywords in rules:
        if any(keyword in text for keyword in keywords):
            tags.append(tag)
        if len(tags) >= 6:
            break
    if not tags and title:
        tags.append(f"#{title[:6]}")
    return tags


def clean_generated_product_tags(tags):
    cleaned = []
    for tag in tags:
        text = str(tag).strip()
        if not text:
            continue
        if not text.startswith("#"):
            text = f"#{text}"
        text = text.replace("，", "").replace(",", "").replace(" ", "")
        label = text.lstrip("#")
        if len(label) > 8:
            label = label[:8]
        if not re.search(r"[A-Za-z0-9\u4e00-\u9fff]", label):
            continue
        normalized = f"#{label}"
        if normalized not in cleaned:
            cleaned.append(normalized)
        if len(cleaned) >= 6:
            break
    return cleaned


def add_point_record(user, change_amount, record_type, remark):
    record = PointRecord(
        user_id=user.id,
        change_amount=change_amount,
        balance_after=user.points_balance,
        record_type=record_type,
        remark=remark,
    )
    db.session.add(record)
    return record


def delete_uploaded_url(url):
    if not url or not url.startswith("/uploads/"):
        return
    if url in {"/uploads/sample_textbook_1.png", "/uploads/sample_textbook_2.png"}:
        return
    relative_path = url.removeprefix("/uploads/").replace("/", os.sep)
    file_path = os.path.abspath(os.path.join(Config.UPLOAD_FOLDER, relative_path))
    upload_root = os.path.abspath(Config.UPLOAD_FOLDER)
    if file_path.startswith(upload_root + os.sep) and os.path.exists(file_path):
        os.remove(file_path)


def delete_user_and_related_data(user):
    product_ids = [product.id for product in Product.query.filter_by(user_id=user.id).all()]
    if product_ids:
        for image in ProductImage.query.filter(ProductImage.product_id.in_(product_ids)).all():
            delete_uploaded_url(image.image_url)
            db.session.delete(image)
        Favorite.query.filter(Favorite.product_id.in_(product_ids)).delete(synchronize_session=False)
        BrowseHistory.query.filter(BrowseHistory.product_id.in_(product_ids)).delete(synchronize_session=False)
        TradeOrder.query.filter(TradeOrder.product_id.in_(product_ids)).delete(synchronize_session=False)
        Product.query.filter(Product.id.in_(product_ids)).delete(synchronize_session=False)

    TradeOrder.query.filter(
        or_(TradeOrder.buyer_id == user.id, TradeOrder.seller_id == user.id)
    ).delete(synchronize_session=False)
    Favorite.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    BrowseHistory.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    PointRecord.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    PointRechargeRequest.query.filter_by(reviewer_id=user.id).update(
        {"reviewer_id": None},
        synchronize_session=False,
    )
    StudentVerificationRequest.query.filter_by(reviewer_id=user.id).update(
        {"reviewer_id": None},
        synchronize_session=False,
    )
    PointRechargeRequest.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    StudentVerificationRequest.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    FriendRequest.query.filter(
        or_(FriendRequest.requester_id == user.id, FriendRequest.receiver_id == user.id)
    ).delete(synchronize_session=False)
    Friendship.query.filter(
        or_(Friendship.user_id == user.id, Friendship.friend_id == user.id)
    ).delete(synchronize_session=False)
    ChatMessage.query.filter(
        or_(ChatMessage.sender_id == user.id, ChatMessage.receiver_id == user.id)
    ).delete(synchronize_session=False)

    delete_uploaded_url(user.avatar)
    db.session.delete(user)


def favorite_product_ids(user_id):
    rows = Favorite.query.with_entities(Favorite.product_id).filter_by(user_id=user_id).all()
    return {product_id for (product_id,) in rows}


def is_friend(user_id, friend_id):
    return Friendship.query.filter_by(user_id=user_id, friend_id=friend_id).first() is not None


def ensure_friendship(user_id, friend_id):
    if not is_friend(user_id, friend_id):
        db.session.add(Friendship(user_id=user_id, friend_id=friend_id))


def user_friends(user):
    return [item.friend for item in Friendship.query.filter_by(user_id=user.id).all()]


def latest_pending_recharge_request(user_id):
    return (
        PointRechargeRequest.query.filter_by(user_id=user_id, status=REQUEST_PENDING)
        .order_by(PointRechargeRequest.create_time.desc())
        .first()
    )


def latest_pending_verification_request(user_id):
    return (
        StudentVerificationRequest.query.filter_by(user_id=user_id, status=REQUEST_PENDING)
        .order_by(StudentVerificationRequest.create_time.desc())
        .first()
    )


def chat_widget_context(user):
    if not user:
        return {
            "chat_friends": [],
            "active_chat_friend": None,
            "chat_messages": [],
            "chat_unread_total": 0,
            "chat_unread_by_friend": {},
            "chat_return_url": request.full_path if request.query_string else request.path,
        }

    friends = user_friends(user)
    friend_ids = {friend.id for friend in friends}
    unread_rows = (
        ChatMessage.query.with_entities(ChatMessage.sender_id, db.func.count(ChatMessage.id))
        .filter_by(receiver_id=user.id, is_read=False)
        .group_by(ChatMessage.sender_id)
        .all()
    )
    unread_by_friend = {sender_id: count for sender_id, count in unread_rows}

    active_friend = None
    messages = []
    chat_with = request.args.get("chat_with", type=int)
    if chat_with in friend_ids:
        active_friend = db.session.get(User, chat_with)
        messages = (
            ChatMessage.query.filter(
                or_(
                    (ChatMessage.sender_id == user.id) & (ChatMessage.receiver_id == chat_with),
                    (ChatMessage.sender_id == chat_with) & (ChatMessage.receiver_id == user.id),
                )
            )
            .order_by(ChatMessage.create_time.asc())
            .limit(80)
            .all()
        )
        ChatMessage.query.filter_by(
            sender_id=chat_with,
            receiver_id=user.id,
            is_read=False,
        ).update({"is_read": True})
        db.session.commit()
        unread_by_friend[chat_with] = 0

    return {
        "chat_friends": friends,
        "active_chat_friend": active_friend,
        "chat_messages": messages,
        "chat_unread_total": sum(unread_by_friend.values()),
        "chat_unread_by_friend": unread_by_friend,
        "chat_return_url": request.full_path if request.query_string else request.path,
    }


def record_product_view(user, product):
    product.view_count += 1
    history = BrowseHistory.query.filter_by(user_id=user.id, product_id=product.id).first()
    if history:
        history.view_count += 1
        history.last_viewed_at = datetime.now()
    else:
        db.session.add(BrowseHistory(user_id=user.id, product_id=product.id))


def admin_dashboard_context():
    products = Product.query.order_by(Product.create_time.desc()).limit(6).all()
    orders = TradeOrder.query.order_by(TradeOrder.create_time.desc()).limit(6).all()
    users = User.query.order_by(User.create_time.desc()).limit(6).all()
    return {
        "user_count": User.query.count(),
        "admin_count": User.query.filter_by(is_admin=True).count(),
        "verified_user_count": User.query.filter_by(is_verified=True).count(),
        "product_count": Product.query.count(),
        "selling_count": Product.query.filter_by(status="在售").count(),
        "sold_count": Product.query.filter_by(status="已售出").count(),
        "removed_count": Product.query.filter_by(status="已下架").count(),
        "order_count": TradeOrder.query.count(),
        "order_points_total": sum(order.points for order in TradeOrder.query.all()),
        "latest_products": products,
        "latest_orders": orders,
        "latest_users": users,
    }


def profile_context(user):
    products = (
        Product.query.filter_by(user_id=user.id)
        .order_by(Product.create_time.desc())
        .all()
    )
    point_records = (
        PointRecord.query.filter_by(user_id=user.id)
        .order_by(PointRecord.create_time.desc())
        .limit(8)
        .all()
    )
    favorites = (
        Favorite.query.filter_by(user_id=user.id)
        .order_by(Favorite.create_time.desc())
        .limit(6)
        .all()
    )
    browse_histories = (
        BrowseHistory.query.filter_by(user_id=user.id)
        .order_by(BrowseHistory.last_viewed_at.desc())
        .limit(6)
        .all()
    )
    purchases = (
        TradeOrder.query.filter_by(buyer_id=user.id)
        .order_by(TradeOrder.create_time.desc())
        .limit(6)
        .all()
    )
    sales = (
        TradeOrder.query.filter_by(seller_id=user.id)
        .order_by(TradeOrder.create_time.desc())
        .limit(6)
        .all()
    )
    incoming_friend_requests = (
        FriendRequest.query.filter_by(receiver_id=user.id, status=FRIEND_REQUEST_PENDING)
        .order_by(FriendRequest.create_time.desc())
        .all()
    )
    outgoing_friend_requests = (
        FriendRequest.query.filter_by(requester_id=user.id, status=FRIEND_REQUEST_PENDING)
        .order_by(FriendRequest.create_time.desc())
        .all()
    )
    recharge_requests = (
        PointRechargeRequest.query.filter_by(user_id=user.id)
        .order_by(PointRechargeRequest.create_time.desc())
        .limit(5)
        .all()
    )
    verification_requests = (
        StudentVerificationRequest.query.filter_by(user_id=user.id)
        .order_by(StudentVerificationRequest.create_time.desc())
        .limit(5)
        .all()
    )
    return {
        "user": user,
        "selling_count": sum(1 for product in products if product.status == "在售"),
        "sold_count": sum(1 for product in products if product.status == "已售出"),
        "removed_count": sum(1 for product in products if product.status == "已下架"),
        "personal_tags": user.personal_tags or "#考研 #教材 #数码爱好者",
        "products": products,
        "point_records": point_records,
        "recharge_plans": RECHARGE_PLANS,
        "favorite_count": Favorite.query.filter_by(user_id=user.id).count(),
        "browse_history_count": BrowseHistory.query.filter_by(user_id=user.id).count(),
        "purchase_count": TradeOrder.query.filter_by(buyer_id=user.id).count(),
        "sale_count": TradeOrder.query.filter_by(seller_id=user.id).count(),
        "completed_order_count": TradeOrder.query.filter(
            TradeOrder.status == ORDER_STATUS_COMPLETED,
            or_(TradeOrder.buyer_id == user.id, TradeOrder.seller_id == user.id),
        ).count(),
        "favorites": favorites,
        "browse_histories": browse_histories,
        "purchases": purchases,
        "sales": sales,
        "friends": user_friends(user),
        "incoming_friend_requests": incoming_friend_requests,
        "outgoing_friend_requests": outgoing_friend_requests,
        "recharge_requests": recharge_requests,
        "verification_requests": verification_requests,
        "pending_recharge_request": latest_pending_recharge_request(user.id),
        "pending_verification_request": latest_pending_verification_request(user.id),
    }


def register_routes(app):
    @app.context_processor
    def inject_template_vars():
        user = current_user()
        context = {
            "current_user_id": session.get("user_id"),
            "current_user_nickname": session.get("nickname"),
            "current_user_is_admin": bool(user and user.is_admin),
        }
        context.update(chat_widget_context(user))
        return context

    @app.route("/")
    @login_required
    def index():
        user = current_user()
        q = request.args.get("q", "").strip()
        search_mode = request.args.get("search_mode", "keyword")
        ai_search_intent = None
        ai_search_exact = search_mode == "ai_exact"
        ai_search_attempted = bool(q and search_mode in {"ai", "ai_exact"})
        ai_status_message = ""
        if ai_search_attempted:
            ai_search_intent = parse_product_search_intent(q, app.config)
            if not ai_search_intent:
                if not app.config.get("AI_API_KEY"):
                    ai_status_message = "AI Key 未配置：请设置 DEEPSEEK_API_KEY 后重启服务。当前已按关键词搜索。"
                elif not app.config.get("AI_ENABLED"):
                    ai_status_message = "AI 服务未启用：请设置 DEEPSEEK_API_KEY 后重启服务。当前已按关键词搜索。"
                else:
                    ai_status_message = "AI 接口调用失败或返回格式异常，当前已按关键词搜索。请检查网络、Key、模型名和 API 额度。"

        products = search_products(q, ai_search_intent, exact=ai_search_exact)
        return render_template(
            "index.html",
            products=products,
            search_keyword=q,
            search_mode=search_mode,
            ai_search_attempted=ai_search_attempted,
            ai_search_exact=ai_search_exact,
            ai_search_used=bool(ai_search_intent),
            ai_status_message=ai_status_message,
            ai_search_summary=(ai_search_intent or {}).get("intent_summary", ""),
            ai_search_keywords=(ai_search_intent or {}).get("keywords", []),
            ai_search_tags=(ai_search_intent or {}).get("tags", []),
            favorite_product_ids=favorite_product_ids(user.id),
            friends=user_friends(user),
        )

    @app.route("/product/<int:product_id>")
    @login_required
    def product_detail(product_id):
        user = current_user()
        product = Product.query.get_or_404(product_id)
        record_product_view(user, product)
        db.session.commit()
        existing_order = TradeOrder.query.filter_by(product_id=product.id).first()
        return render_template(
            "product_detail.html",
            product=product,
            is_favorited=Favorite.query.filter_by(user_id=user.id, product_id=product.id).first() is not None,
            existing_order=existing_order,
            can_view_buyer_info=bool(existing_order and (product.user_id == user.id or user.is_admin)),
        )

    @app.route("/product/<int:product_id>/favorite", methods=["POST"])
    @login_required
    def toggle_favorite(product_id):
        user = current_user()
        product = Product.query.get_or_404(product_id)
        if product.user_id == user.id:
            flash("不能收藏自己发布的商品。", "warning")
            return redirect(request.referrer or url_for("index"))

        favorite = Favorite.query.filter_by(user_id=user.id, product_id=product.id).first()
        if favorite:
            db.session.delete(favorite)
            flash("已取消收藏。", "info")
        else:
            db.session.add(Favorite(user_id=user.id, product_id=product.id))
            flash("已加入收藏。", "success")
        db.session.commit()
        return redirect(request.referrer or url_for("index"))

    @app.route("/product/<int:product_id>/order", methods=["POST"])
    @login_required
    def create_order(product_id):
        buyer = current_user()
        product = Product.query.get_or_404(product_id)
        seller = db.session.get(User, product.user_id)

        if product.user_id == buyer.id:
            flash("不能购买自己发布的商品。", "warning")
            return redirect(url_for("product_detail", product_id=product.id))
        if product.status != "在售":
            flash("该商品当前不可购买。", "danger")
            return redirect(url_for("product_detail", product_id=product.id))
        if TradeOrder.query.filter_by(product_id=product.id).first():
            flash("该商品已经生成订单。", "danger")
            return redirect(url_for("product_detail", product_id=product.id))
        if buyer.points_balance < product.points:
            flash("积分余额不足，请先充值。", "danger")
            return redirect(url_for("product_detail", product_id=product.id))
        if not buyer.shipping_address:
            flash("请先在个人中心填写收货地址，再兑换商品。", "warning")
            return redirect(url_for("profile"))

        buyer.points_balance -= product.points
        seller.points_balance += product.points
        product.status = "已售出"
        order = TradeOrder(
            buyer_id=buyer.id,
            seller_id=seller.id,
            product_id=product.id,
            points=product.points,
            status=ORDER_STATUS_COMPLETED,
        )
        db.session.add(order)
        add_point_record(buyer, -product.points, "购买", f"购买商品：{product.title}")
        add_point_record(seller, product.points, "售出", f"售出商品：{product.title}")
        db.session.commit()
        flash("交易完成，积分已结算。", "success")
        return redirect(url_for("profile"))

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if session.get("user_id") and request.method == "GET":
            return redirect(url_for("index"))

        if request.method == "POST":
            account = request.form.get("account", "").strip()
            nickname = request.form.get("nickname", "").strip()
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")

            error = validate_register_form(account, nickname, password, confirm_password)
            if error:
                flash(error, "danger")
                return render_template("register.html", account=account, nickname=nickname)

            user = User(
                account=account,
                nickname=nickname,
                password=generate_password_hash(password),
            )
            db.session.add(user)
            db.session.commit()
            flash("注册成功，请登录。", "success")
            return redirect(url_for("login"))

        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        next_url = request.args.get("next") or request.form.get("next") or url_for("index")
        if session.get("user_id") and request.method == "GET":
            return redirect(url_for("index"))

        if request.method == "POST":
            account = request.form.get("account", "").strip()
            password = request.form.get("password", "")
            user = User.query.filter_by(account=account).first()

            if not user:
                flash("用户名不存在", "danger")
                return render_template("login.html", account=account, next_url=next_url)
            if not check_password_hash(user.password, password):
                flash("密码错误", "danger")
                return render_template("login.html", account=account, next_url=next_url)

            session["user_id"] = user.id
            session["nickname"] = user.nickname
            flash("登录成功。", "success")
            if not user.contact:
                flash("请到个人中心完善手机号/联系方式，避免忘记密码后无法自助找回。", "warning")
            return redirect(next_url)

        return render_template("login.html", next_url=next_url)

    @app.route("/forgot-password", methods=["GET", "POST"])
    def forgot_password():
        if request.method == "POST":
            account = request.form.get("account", "").strip()
            contact = request.form.get("contact", "").strip()
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")

            error, user = validate_password_reset_form(account, contact, password, confirm_password)
            if error:
                flash(error, "danger")
                return render_template("forgot_password.html", account=account, contact=contact)

            user.password = generate_password_hash(password)
            db.session.commit()
            flash("密码已重置，请使用新密码登录。", "success")
            return redirect(url_for("login"))

        return render_template("forgot_password.html")

    @app.route("/logout")
    def logout():
        session.clear()
        flash("已退出登录。", "info")
        return redirect(url_for("login"))

    @app.route("/profile")
    @login_required
    def profile():
        return render_template("profile.html", **profile_context(current_user()))

    @app.route("/admin")
    @admin_required
    def admin_dashboard():
        return render_template("admin/dashboard.html", **admin_dashboard_context())

    @app.route("/admin/users")
    @admin_required
    def admin_users():
        q = request.args.get("q", "").strip()
        query = User.query
        if q:
            like_text = f"%{q}%"
            query = query.filter(
                or_(
                    User.account.like(like_text),
                    User.nickname.like(like_text),
                    User.real_name.like(like_text),
                    User.school.like(like_text),
                    User.contact.like(like_text),
                )
            )
        users = query.order_by(User.create_time.desc()).all()
        return render_template("admin/users.html", users=users, search_keyword=q)

    @app.route("/admin/users/<int:user_id>/toggle-admin", methods=["POST"])
    @admin_required
    def admin_toggle_user_admin(user_id):
        operator = current_user()
        user = User.query.get_or_404(user_id)
        if user.id == operator.id:
            flash("不能取消自己的管理员权限。", "warning")
            return redirect(url_for("admin_users"))
        if user.is_admin and User.query.filter_by(is_admin=True).count() <= 1:
            flash("系统至少需要保留一个管理员账号。", "danger")
            return redirect(url_for("admin_users"))

        user.is_admin = not user.is_admin
        db.session.commit()
        flash("管理员权限已更新。", "success")
        return redirect(url_for("admin_users"))

    @app.route("/admin/users/<int:user_id>/toggle-verified", methods=["POST"])
    @admin_required
    def admin_toggle_user_verified(user_id):
        user = User.query.get_or_404(user_id)
        user.is_verified = not user.is_verified
        db.session.commit()
        flash("用户认证状态已更新。", "success")
        return redirect(url_for("admin_users"))

    @app.route("/admin/users/<int:user_id>/points", methods=["POST"])
    @admin_required
    def admin_adjust_user_points(user_id):
        user = User.query.get_or_404(user_id)
        delta_text = request.form.get("delta", "").strip()
        remark = request.form.get("remark", "").strip() or "管理员调整积分"
        try:
            delta = int(delta_text)
        except ValueError:
            flash("积分调整值必须是整数。", "danger")
            return redirect(url_for("admin_users"))
        if delta == 0:
            flash("积分调整值不能为 0。", "warning")
            return redirect(url_for("admin_users"))
        if user.points_balance + delta < 0:
            flash("调整后积分不能小于 0。", "danger")
            return redirect(url_for("admin_users"))

        user.points_balance += delta
        add_point_record(user, delta, "后台调整", remark)
        db.session.commit()
        flash("用户积分已调整。", "success")
        return redirect(url_for("admin_users"))

    @app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
    @admin_required
    def admin_delete_user(user_id):
        operator = current_user()
        user = User.query.get_or_404(user_id)
        if user.id == operator.id:
            flash("不能删除当前登录的管理员账号。", "warning")
            return redirect(url_for("admin_users"))
        if user.is_admin and User.query.filter_by(is_admin=True).count() <= 1:
            flash("系统至少需要保留一个管理员账号。", "danger")
            return redirect(url_for("admin_users"))

        nickname = user.nickname
        delete_user_and_related_data(user)
        db.session.commit()
        flash(f"用户 {nickname} 及其发布、购买、好友、聊天等关联信息已删除。", "success")
        return redirect(url_for("admin_users"))

    @app.route("/admin/points")
    @admin_required
    def admin_points():
        status = request.args.get("status", "").strip()
        query = PointRechargeRequest.query
        if status in {REQUEST_PENDING, REQUEST_APPROVED, REQUEST_REJECTED}:
            query = query.filter_by(status=status)
        requests = query.order_by(PointRechargeRequest.create_time.desc()).all()
        return render_template(
            "admin/points.html",
            requests=requests,
            selected_status=status,
            request_status_options=(REQUEST_PENDING, REQUEST_APPROVED, REQUEST_REJECTED),
        )

    @app.route("/admin/points/<int:request_id>/review", methods=["POST"])
    @admin_required
    def admin_review_point_request(request_id):
        operator = current_user()
        point_request = PointRechargeRequest.query.get_or_404(request_id)
        action = request.form.get("action", "")
        admin_remark = request.form.get("admin_remark", "").strip() or None

        if point_request.status != REQUEST_PENDING:
            flash("该积分申请已处理。", "info")
            return redirect(url_for("admin_points"))

        if action == "approve":
            user = db.session.get(User, point_request.user_id)
            user.points_balance += point_request.points
            point_request.status = REQUEST_APPROVED
            add_point_record(user, point_request.points, "充值审核", f"管理员通过充值申请：{point_request.points} 积分")
            flash("积分申请已通过，积分已发放。", "success")
        elif action == "reject":
            point_request.status = REQUEST_REJECTED
            flash("积分申请已拒绝。", "info")
        else:
            flash("积分申请操作不合法。", "danger")
            return redirect(url_for("admin_points"))

        point_request.admin_remark = admin_remark
        point_request.reviewer_id = operator.id
        point_request.review_time = datetime.now()
        db.session.commit()
        return redirect(url_for("admin_points"))

    @app.route("/admin/verifications")
    @admin_required
    def admin_verifications():
        status = request.args.get("status", "").strip()
        query = StudentVerificationRequest.query
        if status in {REQUEST_PENDING, REQUEST_APPROVED, REQUEST_REJECTED}:
            query = query.filter_by(status=status)
        requests = query.order_by(StudentVerificationRequest.create_time.desc()).all()
        return render_template(
            "admin/verifications.html",
            requests=requests,
            selected_status=status,
            request_status_options=(REQUEST_PENDING, REQUEST_APPROVED, REQUEST_REJECTED),
        )

    @app.route("/admin/verifications/<int:request_id>/review", methods=["POST"])
    @admin_required
    def admin_review_verification_request(request_id):
        operator = current_user()
        verification_request = StudentVerificationRequest.query.get_or_404(request_id)
        action = request.form.get("action", "")
        admin_remark = request.form.get("admin_remark", "").strip() or None

        if verification_request.status != REQUEST_PENDING:
            flash("该认证申请已处理。", "info")
            return redirect(url_for("admin_verifications"))

        user = db.session.get(User, verification_request.user_id)
        if action == "approve":
            user.real_name = verification_request.real_name
            user.student_id = verification_request.student_id
            user.is_verified = True
            verification_request.status = REQUEST_APPROVED
            flash("学生认证申请已通过。", "success")
        elif action == "reject":
            verification_request.status = REQUEST_REJECTED
            flash("学生认证申请已拒绝。", "info")
        else:
            flash("认证申请操作不合法。", "danger")
            return redirect(url_for("admin_verifications"))

        verification_request.admin_remark = admin_remark
        verification_request.reviewer_id = operator.id
        verification_request.review_time = datetime.now()
        db.session.commit()
        return redirect(url_for("admin_verifications"))

    @app.route("/admin/products")
    @admin_required
    def admin_products():
        q = request.args.get("q", "").strip()
        status = request.args.get("status", "").strip()
        query = Product.query
        if status in PRODUCT_STATUSES:
            query = query.filter_by(status=status)
        if q:
            like_text = f"%{q}%"
            query = query.filter(
                or_(
                    Product.title.like(like_text),
                    Product.description.like(like_text),
                    Product.tags.like(like_text),
                )
            )
        products = query.order_by(Product.create_time.desc()).all()
        return render_template(
            "admin/products.html",
            products=products,
            product_status_options=PRODUCT_STATUS_OPTIONS,
            search_keyword=q,
            selected_status=status,
        )

    @app.route("/admin/products/<int:product_id>/status", methods=["POST"])
    @admin_required
    def admin_update_product_status(product_id):
        product = Product.query.get_or_404(product_id)
        status = request.form.get("status", "").strip()
        if status not in PRODUCT_STATUSES:
            flash("商品状态不合法。", "danger")
            return redirect(url_for("admin_products"))
        product.status = status
        db.session.commit()
        flash("商品状态已更新。", "success")
        return redirect(request.referrer or url_for("admin_products"))

    @app.route("/admin/orders")
    @admin_required
    def admin_orders():
        q = request.args.get("q", "").strip()
        query = TradeOrder.query.join(Product, TradeOrder.product_id == Product.id)
        if q:
            like_text = f"%{q}%"
            query = query.join(User, TradeOrder.buyer_id == User.id).filter(
                or_(
                    Product.title.like(like_text),
                    User.account.like(like_text),
                    User.nickname.like(like_text),
                )
            )
        orders = query.order_by(TradeOrder.create_time.desc()).all()
        return render_template("admin/orders.html", orders=orders, search_keyword=q)

    @app.route("/friends/request", methods=["POST"])
    @login_required
    def send_friend_request():
        user = current_user()
        keyword = request.form.get("account", "").strip()
        targets = []
        if keyword:
            targets = User.query.filter(
                or_(
                    User.nickname == keyword,
                    User.real_name == keyword,
                    User.account == keyword,
                )
            ).all()

        if not keyword:
            flash("请输入要添加的用户昵称、真实姓名或用户名。", "danger")
            return redirect(url_for("profile"))
        if not targets:
            flash("没有找到匹配的用户。", "danger")
            return redirect(url_for("profile"))
        filtered_targets = [target for target in targets if target.id != user.id]
        if not filtered_targets:
            flash("不能添加自己为好友。", "warning")
            return redirect(url_for("profile"))
        if len(filtered_targets) > 1:
            flash("找到多个同名用户，请改用用户名精确添加。", "warning")
            return redirect(url_for("profile"))
        target = filtered_targets[0]

        return create_friend_request_for_user(user, target)

    @app.route("/friends/request/user/<int:user_id>", methods=["POST"])
    @login_required
    def send_friend_request_to_user(user_id):
        user = current_user()
        target = User.query.get_or_404(user_id)
        return create_friend_request_for_user(user, target, redirect_to=request.referrer or url_for("index"))

    def create_friend_request_for_user(user, target, redirect_to=None):
        redirect_to = redirect_to or url_for("profile")
        if target.id == user.id:
            flash("不能添加自己为好友。", "warning")
            return redirect(redirect_to)
        if is_friend(user.id, target.id):
            flash("你们已经是好友。", "info")
            return redirect(redirect_to)

        reverse_request = FriendRequest.query.filter_by(
            requester_id=target.id,
            receiver_id=user.id,
            status=FRIEND_REQUEST_PENDING,
        ).first()
        if reverse_request:
            reverse_request.status = FRIEND_REQUEST_ACCEPTED
            ensure_friendship(user.id, target.id)
            ensure_friendship(target.id, user.id)
            db.session.commit()
            flash("已通过对方的好友申请。", "success")
            return redirect(redirect_to)

        existing_request = FriendRequest.query.filter_by(
            requester_id=user.id,
            receiver_id=target.id,
            status=FRIEND_REQUEST_PENDING,
        ).first()
        if existing_request:
            flash("好友申请已发送，请等待对方处理。", "info")
            return redirect(redirect_to)

        db.session.add(
            FriendRequest(
                requester_id=user.id,
                receiver_id=target.id,
                status=FRIEND_REQUEST_PENDING,
            )
        )
        db.session.commit()
        flash("好友申请已发送。", "success")
        return redirect(redirect_to)

    @app.route("/friends/request/<int:request_id>/respond", methods=["POST"])
    @login_required
    def respond_friend_request(request_id):
        user = current_user()
        friend_request = FriendRequest.query.filter_by(
            id=request_id,
            receiver_id=user.id,
            status=FRIEND_REQUEST_PENDING,
        ).first_or_404()
        action = request.form.get("action", "")

        if action == "accept":
            friend_request.status = FRIEND_REQUEST_ACCEPTED
            ensure_friendship(friend_request.requester_id, friend_request.receiver_id)
            ensure_friendship(friend_request.receiver_id, friend_request.requester_id)
            flash("已同意好友申请。", "success")
        elif action == "reject":
            friend_request.status = FRIEND_REQUEST_REJECTED
            flash("已拒绝好友申请。", "info")
        else:
            flash("好友申请操作不合法。", "danger")
            return redirect(url_for("profile"))

        db.session.commit()
        return redirect(url_for("profile"))

    @app.route("/friends/request/<int:request_id>/cancel", methods=["POST"])
    @login_required
    def cancel_friend_request(request_id):
        user = current_user()
        friend_request = FriendRequest.query.filter_by(
            id=request_id,
            requester_id=user.id,
            status=FRIEND_REQUEST_PENDING,
        ).first_or_404()
        db.session.delete(friend_request)
        db.session.commit()
        flash("好友申请已撤回。", "info")
        return redirect(url_for("profile"))

    @app.route("/friends/<int:friend_id>/remove", methods=["POST"])
    @login_required
    def remove_friend(friend_id):
        user = current_user()
        if friend_id == user.id:
            flash("不能删除自己。", "warning")
            return redirect(url_for("profile"))

        deleted = False
        for item in Friendship.query.filter_by(user_id=user.id, friend_id=friend_id).all():
            db.session.delete(item)
            deleted = True
        for item in Friendship.query.filter_by(user_id=friend_id, friend_id=user.id).all():
            db.session.delete(item)
            deleted = True

        if deleted:
            db.session.commit()
            flash("好友已删除。", "success")
        else:
            flash("好友关系不存在。", "info")
        return redirect(url_for("profile"))

    @app.route("/chat/send/<int:friend_id>", methods=["POST"])
    @login_required
    def send_chat_message(friend_id):
        user = current_user()
        if not is_friend(user.id, friend_id):
            flash("只能给好友发送消息。", "danger")
            return redirect(request.form.get("return_url") or url_for("index"))

        content = request.form.get("content", "").strip()
        if not content:
            flash("消息内容不能为空。", "warning")
            return redirect(request.form.get("return_url") or url_for("index"))
        if len(content) > 500:
            flash("单条消息不能超过 500 个字符。", "danger")
            return redirect(request.form.get("return_url") or url_for("index"))

        db.session.add(
            ChatMessage(
                sender_id=user.id,
                receiver_id=friend_id,
                content=content,
            )
        )
        db.session.commit()

        return_url = request.form.get("return_url") or url_for("index")
        separator = "&" if "?" in return_url else "?"
        if "chat_with=" not in return_url:
            return_url = f"{return_url}{separator}chat_with={friend_id}"
        return redirect(return_url)

    @app.route("/profile/avatar", methods=["POST"])
    @login_required
    def update_avatar():
        user = current_user()
        avatar_file = request.files.get("avatar")
        if not avatar_file or not avatar_file.filename:
            flash("请选择要上传的头像图片。", "danger")
            return redirect(url_for("profile"))
        if not allowed_image(avatar_file.filename):
            flash("头像只支持 jpg、jpeg、png、gif 格式。", "danger")
            return redirect(url_for("profile"))

        _, avatar_url = save_uploaded_image(avatar_file, "avatars")
        user.avatar = avatar_url
        db.session.commit()
        flash("头像已更新。", "success")
        return redirect(url_for("profile"))

    @app.route("/profile/update-info", methods=["POST"])
    @login_required
    def update_profile_info():
        user = current_user()
        nickname = request.form.get("nickname", "").strip()
        real_name = request.form.get("real_name", "").strip()
        contact = request.form.get("contact", "").strip()
        school = request.form.get("school", "").strip()
        shipping_address = request.form.get("shipping_address", "").strip()
        personal_tags = request.form.get("personal_tags", "").strip()

        if not nickname:
            flash("用户名不能为空。", "danger")
            return redirect(url_for("profile"))
        user.nickname = nickname
        user.real_name = real_name or None
        user.contact = contact or None
        user.school = school or None
        user.shipping_address = shipping_address or None
        user.personal_tags = " ".join(normalize_tags(personal_tags)) if personal_tags else None
        session["nickname"] = user.nickname
        db.session.commit()
        flash("用户资料已保存。", "success")
        return redirect(url_for("profile"))

    @app.route("/profile/change-password", methods=["POST"])
    @login_required
    def change_password():
        user = current_user()
        old_password = request.form.get("old_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not check_password_hash(user.password, old_password):
            flash("原密码错误。", "danger")
            return redirect(url_for("profile"))
        if len(new_password) < 6:
            flash("新密码长度不能少于 6 位。", "danger")
            return redirect(url_for("profile"))
        if new_password != confirm_password:
            flash("两次输入的新密码不一致。", "danger")
            return redirect(url_for("profile"))

        user.password = generate_password_hash(new_password)
        db.session.commit()
        flash("密码已修改，请使用新密码。", "success")
        return redirect(url_for("profile"))

    @app.route("/profile/verify-student", methods=["POST"])
    @login_required
    def verify_student():
        user = current_user()
        real_name = request.form.get("real_name", "").strip()
        student_id = request.form.get("student_id", "").strip()
        pending_request = latest_pending_verification_request(user.id)
        if pending_request:
            flash("已有待审核的学号认证申请，请等待管理员处理。", "info")
            return redirect(url_for("profile"))
        if not real_name:
            flash("请输入真实姓名。", "danger")
            return redirect(url_for("profile"))
        if len(student_id) < 5:
            flash("学号长度不能少于 5 位。", "danger")
            return redirect(url_for("profile"))
        db.session.add(
            StudentVerificationRequest(
                user_id=user.id,
                real_name=real_name,
                student_id=student_id,
                status=REQUEST_PENDING,
            )
        )
        db.session.commit()
        flash("学号认证申请已提交，请等待管理员审核。", "success")
        return redirect(url_for("profile"))

    @app.route("/profile/recharge", methods=["POST"])
    @login_required
    def recharge_points():
        user = current_user()
        amount = request.form.get("amount", "")
        points = RECHARGE_PLANS.get(amount)
        if points is None:
            flash("请选择有效的充值档位。", "danger")
            return redirect(url_for("profile"))
        if latest_pending_recharge_request(user.id):
            flash("已有待审核的积分申请，请等待管理员处理。", "info")
            return redirect(url_for("profile"))

        request_record = PointRechargeRequest(
            user_id=user.id,
            amount=amount,
            points=points,
            status=REQUEST_PENDING,
            remark=f"{amount}元兑换{points}积分",
        )
        db.session.add(request_record)
        db.session.commit()
        flash(f"积分申请已提交，管理员通过后将增加 {points} 积分。", "success")
        return redirect(url_for("profile"))

    @app.route("/profile/product/<int:product_id>/status", methods=["POST"])
    @login_required
    def update_product_status(product_id):
        user = current_user()
        product = Product.query.filter_by(id=product_id, user_id=user.id).first_or_404()
        status = request.form.get("status", "").strip()
        if status not in PRODUCT_STATUSES:
            flash("商品状态不合法。", "danger")
            return redirect(url_for("profile"))
        product.status = status
        db.session.commit()
        flash("商品状态已更新。", "success")
        return redirect(url_for("profile"))

    @app.route("/publish", methods=["GET", "POST"])
    @login_required
    def publish():
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            points_text = request.form.get("points", "").strip()
            raw_tags = request.form.get("tags", "").strip()
            image_files = [item for item in request.files.getlist("images") if item and item.filename]

            error, points, tags = validate_product_form(title, description, points_text, raw_tags, image_files)
            if error:
                flash(error, "danger")
                return render_template(
                    "publish.html",
                    form_data={
                        "title": title,
                        "description": description,
                        "points": points_text,
                        "tags": raw_tags,
                    },
                )

            product = Product(
                user_id=session["user_id"],
                title=title,
                description=description,
                points=points,
                tags=" ".join(tags),
                status="在售",
            )
            db.session.add(product)
            db.session.flush()

            saved_filenames = []
            try:
                for index, image_file in enumerate(image_files):
                    filename, image_url = save_product_image(image_file)
                    saved_filenames.append(filename)
                    db.session.add(
                        ProductImage(
                            product_id=product.id,
                            image_url=image_url,
                            sort_order=index,
                        )
                    )
                db.session.commit()
            except Exception:
                db.session.rollback()
                for filename in saved_filenames:
                    file_path = os.path.join(Config.UPLOAD_FOLDER, filename)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                flash("商品发布失败，请稍后重试。", "danger")
                return render_template("publish.html")

            flash("商品发布成功。", "success")
            return redirect(url_for("index"))

        return render_template("publish.html")

    @app.route("/ai/product-tags", methods=["POST"])
    @login_required
    def ai_product_tags():
        data = request.get_json(silent=True) or {}
        title = str(data.get("title") or "").strip()
        description = str(data.get("description") or "").strip()
        if not title and not description:
            return jsonify({"ok": False, "message": "请先填写商品标题或描述。"}), 400

        tags = clean_generated_product_tags(generate_product_tags(title, description, app.config))
        fallback_tags = fallback_product_tags(title, description)
        for tag in fallback_tags:
            if len(tags) >= 6:
                break
            if tag not in tags:
                tags.append(tag)
        if not tags:
            tags = fallback_tags
        if not tags:
            return jsonify({"ok": False, "message": "暂时无法生成标签，请补充更具体的商品描述。"}), 400
        return jsonify({"ok": True, "tags": tags})

    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


def register_commands(app):
    @app.cli.command("init-db")
    def init_db_command():
        """Create database tables and add missing columns for local SQLite."""
        ensure_database_schema()
        click.echo("数据库初始化完成。")

    @app.cli.command("create-admin")
    @click.option("--account", prompt=True, help="管理员账号")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True, help="管理员密码")
    @click.option("--nickname", default="管理员", show_default=True, help="管理员昵称")
    def create_admin_command(account, password, nickname):
        """Create or promote a local admin account."""
        account = account.strip()
        nickname = nickname.strip() or "管理员"
        if len(password) < 6:
            click.echo("管理员密码不能少于 6 位。")
            return

        user = User.query.filter_by(account=account).first()
        if user:
            user.nickname = nickname
            user.password = generate_password_hash(password)
            user.is_admin = True
            user.is_verified = True
            message = "已更新并授权管理员账号。"
        else:
            user = User(
                account=account,
                nickname=nickname,
                password=generate_password_hash(password),
                is_admin=True,
                is_verified=True,
            )
            db.session.add(user)
            message = "已创建管理员账号。"
        db.session.commit()
        click.echo(message)


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
