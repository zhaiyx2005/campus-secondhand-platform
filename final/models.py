from datetime import datetime

from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    account = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    nickname = db.Column(db.String(80), nullable=False)
    real_name = db.Column(db.String(80), nullable=True)
    avatar = db.Column(db.String(255), nullable=True)
    school = db.Column(db.String(120), nullable=True)
    contact = db.Column(db.String(120), nullable=True)
    shipping_address = db.Column(db.String(255), nullable=True)
    student_id = db.Column(db.String(60), nullable=True)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    points_balance = db.Column(db.Integer, default=250, nullable=False)
    credit_score = db.Column(db.Integer, default=98, nullable=False)
    personal_tags = db.Column(db.String(255), nullable=True)
    create_time = db.Column(db.DateTime, default=datetime.now, nullable=False)
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    __table_args__ = (
        db.Index("ix_user_create_time", "create_time"),
        db.Index("ix_user_admin_verified", "is_admin", "is_verified"),
    )

    products = db.relationship("Product", back_populates="user", cascade="all, delete-orphan")
    point_records = db.relationship("PointRecord", back_populates="user", cascade="all, delete-orphan")
    point_recharge_requests = db.relationship(
        "PointRechargeRequest",
        foreign_keys="PointRechargeRequest.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    reviewed_point_recharge_requests = db.relationship(
        "PointRechargeRequest",
        foreign_keys="PointRechargeRequest.reviewer_id",
        back_populates="reviewer",
    )
    student_verification_requests = db.relationship(
        "StudentVerificationRequest",
        foreign_keys="StudentVerificationRequest.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    reviewed_student_verification_requests = db.relationship(
        "StudentVerificationRequest",
        foreign_keys="StudentVerificationRequest.reviewer_id",
        back_populates="reviewer",
    )
    favorites = db.relationship("Favorite", back_populates="user", cascade="all, delete-orphan")
    browse_histories = db.relationship("BrowseHistory", back_populates="user", cascade="all, delete-orphan")
    purchases = db.relationship("TradeOrder", foreign_keys="TradeOrder.buyer_id", back_populates="buyer")
    sales = db.relationship("TradeOrder", foreign_keys="TradeOrder.seller_id", back_populates="seller")
    sent_friend_requests = db.relationship(
        "FriendRequest",
        foreign_keys="FriendRequest.requester_id",
        back_populates="requester",
        cascade="all, delete-orphan",
    )
    received_friend_requests = db.relationship(
        "FriendRequest",
        foreign_keys="FriendRequest.receiver_id",
        back_populates="receiver",
        cascade="all, delete-orphan",
    )
    friendships = db.relationship(
        "Friendship",
        foreign_keys="Friendship.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    sent_chat_messages = db.relationship(
        "ChatMessage",
        foreign_keys="ChatMessage.sender_id",
        back_populates="sender",
        cascade="all, delete-orphan",
    )
    received_chat_messages = db.relationship(
        "ChatMessage",
        foreign_keys="ChatMessage.receiver_id",
        back_populates="receiver",
        cascade="all, delete-orphan",
    )


class Product(db.Model):
    __tablename__ = "product"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    points = db.Column(db.Integer, nullable=False)
    tags = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default="在售", nullable=False)
    view_count = db.Column(db.Integer, default=0, nullable=False)
    create_time = db.Column(db.DateTime, default=datetime.now, nullable=False)
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    __table_args__ = (
        db.Index("ix_product_status_create_time", "status", "create_time"),
        db.Index("ix_product_user_status", "user_id", "status"),
        db.Index("ix_product_points_status", "points", "status"),
    )

    user = db.relationship("User", back_populates="products")
    images = db.relationship(
        "ProductImage",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductImage.sort_order",
    )
    favorites = db.relationship("Favorite", back_populates="product", cascade="all, delete-orphan")
    browse_histories = db.relationship("BrowseHistory", back_populates="product", cascade="all, delete-orphan")
    orders = db.relationship("TradeOrder", back_populates="product")

    @property
    def first_image_url(self):
        if self.images:
            return self.images[0].image_url
        return ""

    @property
    def tag_list(self):
        return [tag for tag in self.tags.split(" ") if tag]


class ProductImage(db.Model):
    __tablename__ = "product_image"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    image_url = db.Column(db.String(255), nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    create_time = db.Column(db.DateTime, default=datetime.now, nullable=False)

    __table_args__ = (db.Index("ix_product_image_product_sort", "product_id", "sort_order"),)

    product = db.relationship("Product", back_populates="images")


class PointRecord(db.Model):
    __tablename__ = "point_record"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    change_amount = db.Column(db.Integer, nullable=False)
    balance_after = db.Column(db.Integer, nullable=False)
    record_type = db.Column(db.String(30), nullable=False)
    remark = db.Column(db.String(255), nullable=True)
    create_time = db.Column(db.DateTime, default=datetime.now, nullable=False)

    __table_args__ = (db.Index("ix_point_record_user_create_time", "user_id", "create_time"),)

    user = db.relationship("User", back_populates="point_records")


class PointRechargeRequest(db.Model):
    __tablename__ = "point_recharge_request"
    __table_args__ = (db.Index("ix_recharge_user_status_time", "user_id", "status", "create_time"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    amount = db.Column(db.String(20), nullable=False)
    points = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default="待审核", nullable=False)
    remark = db.Column(db.String(255), nullable=True)
    admin_remark = db.Column(db.String(255), nullable=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    create_time = db.Column(db.DateTime, default=datetime.now, nullable=False)
    review_time = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", foreign_keys=[user_id], back_populates="point_recharge_requests")
    reviewer = db.relationship(
        "User",
        foreign_keys=[reviewer_id],
        back_populates="reviewed_point_recharge_requests",
    )


class StudentVerificationRequest(db.Model):
    __tablename__ = "student_verification_request"
    __table_args__ = (db.Index("ix_verification_user_status_time", "user_id", "status", "create_time"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    real_name = db.Column(db.String(80), nullable=False)
    student_id = db.Column(db.String(60), nullable=False)
    status = db.Column(db.String(20), default="待审核", nullable=False)
    admin_remark = db.Column(db.String(255), nullable=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    create_time = db.Column(db.DateTime, default=datetime.now, nullable=False)
    review_time = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", foreign_keys=[user_id], back_populates="student_verification_requests")
    reviewer = db.relationship(
        "User",
        foreign_keys=[reviewer_id],
        back_populates="reviewed_student_verification_requests",
    )


class Favorite(db.Model):
    __tablename__ = "favorite"
    __table_args__ = (db.UniqueConstraint("user_id", "product_id", name="uq_favorite_user_product"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, index=True)
    create_time = db.Column(db.DateTime, default=datetime.now, nullable=False)

    user = db.relationship("User", back_populates="favorites")
    product = db.relationship("Product", back_populates="favorites")


class BrowseHistory(db.Model):
    __tablename__ = "browse_history"
    __table_args__ = (db.UniqueConstraint("user_id", "product_id", name="uq_browse_history_user_product"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, index=True)
    view_count = db.Column(db.Integer, default=1, nullable=False)
    create_time = db.Column(db.DateTime, default=datetime.now, nullable=False)
    last_viewed_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    user = db.relationship("User", back_populates="browse_histories")
    product = db.relationship("Product", back_populates="browse_histories")


class TradeOrder(db.Model):
    __tablename__ = "trade_order"

    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, index=True, unique=True)
    points = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default="已完成", nullable=False)
    create_time = db.Column(db.DateTime, default=datetime.now, nullable=False)
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    __table_args__ = (db.Index("ix_trade_order_create_time", "create_time"),)

    buyer = db.relationship("User", foreign_keys=[buyer_id], back_populates="purchases")
    seller = db.relationship("User", foreign_keys=[seller_id], back_populates="sales")
    product = db.relationship("Product", back_populates="orders")


class FriendRequest(db.Model):
    __tablename__ = "friend_request"
    __table_args__ = (
        db.UniqueConstraint("requester_id", "receiver_id", "status", name="uq_friend_request_status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    status = db.Column(db.String(20), default="待处理", nullable=False)
    create_time = db.Column(db.DateTime, default=datetime.now, nullable=False)
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    requester = db.relationship("User", foreign_keys=[requester_id], back_populates="sent_friend_requests")
    receiver = db.relationship("User", foreign_keys=[receiver_id], back_populates="received_friend_requests")


class Friendship(db.Model):
    __tablename__ = "friendship"
    __table_args__ = (db.UniqueConstraint("user_id", "friend_id", name="uq_friendship_pair"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    friend_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    create_time = db.Column(db.DateTime, default=datetime.now, nullable=False)

    user = db.relationship("User", foreign_keys=[user_id], back_populates="friendships")
    friend = db.relationship("User", foreign_keys=[friend_id])


class ChatMessage(db.Model):
    __tablename__ = "chat_message"
    __table_args__ = (
        db.Index("ix_chat_receiver_read_time", "receiver_id", "is_read", "create_time"),
        db.Index("ix_chat_pair_time", "sender_id", "receiver_id", "create_time"),
    )

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    create_time = db.Column(db.DateTime, default=datetime.now, nullable=False)

    sender = db.relationship("User", foreign_keys=[sender_id], back_populates="sent_chat_messages")
    receiver = db.relationship("User", foreign_keys=[receiver_id], back_populates="received_chat_messages")
