import math

from sqlalchemy import or_

from models import Product


SYNONYM_GROUPS = [
    ("吃", "吃的", "可吃", "可以吃", "能吃", "食用", "可食用", "食品", "食物", "零食", "水果", "蔬菜", "饮料", "餐饮"),
    ("书", "书籍", "教材", "课本", "资料", "复习资料", "参考书"),
    ("高数", "高等数学", "微积分", "大学数学"),
    ("电脑", "笔记本", "台式机", "主机", "显示器", "键盘", "鼠标", "数码", "电子产品"),
    ("衣服", "服装", "上衣", "外套", "裙子", "裤子", "鞋", "穿的"),
    ("运动", "健身", "球", "球拍", "跑步", "训练"),
]


def search_products(query_text="", intent=None, exact=False, limit=24, offset=0):
    """Return one bounded catalogue page.

    AI ranking uses a bounded candidate window so a large catalogue cannot
    force an unbounded Python sort for every request.
    """
    # 101 lets callers request a page of 100 plus one sentinel row.
    limit = max(1, min(int(limit or 24), 101))
    offset = max(0, int(offset or 0))
    base_query = Product.query.filter_by(status="在售")
    if not query_text:
        return base_query.order_by(Product.create_time.desc()).offset(offset).limit(limit).all()

    if not intent:
        if exact:
            return exact_keyword_search_products(base_query, query_text, limit, offset)
        return keyword_search_products(base_query, query_text, limit, offset)

    terms = _search_terms(query_text, intent)
    # Ranking is intentionally bounded. A very deep AI page is treated as
    # empty rather than turning one request into an unbounded database read.
    candidates = _candidate_products(base_query, terms, intent, 5000)
    if not candidates:
        candidates = _apply_point_filters(base_query.order_by(Product.create_time.desc()), intent).limit(5000).all()

    condition_groups = _exact_condition_groups(query_text, intent) if exact else []
    scored_products = []
    for product in candidates:
        if condition_groups and not _matches_condition_groups(product, condition_groups):
            continue
        score = _score_product(product, query_text, intent, terms)
        if score > 0:
            scored_products.append((score, product.create_time, product))

    scored_products.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [product for _, _, product in scored_products[offset : offset + limit]]


def keyword_search_products(base_query, query_text, limit=24, offset=0):
    like_text = f"%{query_text}%"
    return (
        base_query.filter(
            or_(
                Product.title.like(like_text),
                Product.description.like(like_text),
                Product.tags.like(like_text),
            )
        )
        .order_by(Product.create_time.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def exact_keyword_search_products(base_query, query_text, limit=24, offset=0):
    groups = _exact_condition_groups(query_text, None)
    products = base_query.order_by(Product.create_time.desc()).limit(5000).all()
    if not groups:
        return products[offset : offset + limit]
    return [product for product in products if _matches_condition_groups(product, groups)][offset : offset + limit]


def _candidate_products(base_query, terms, intent, limit=5000):
    if not terms:
        return _apply_point_filters(base_query.order_by(Product.create_time.desc()), intent).limit(limit).all()

    filters = []
    for term in terms:
        like_text = f"%{term}%"
        filters.extend(
            [
                Product.title.like(like_text),
                Product.description.like(like_text),
                Product.tags.like(like_text),
            ]
        )

    query = base_query.filter(or_(*filters))
    return _apply_point_filters(query, intent).order_by(Product.create_time.desc()).limit(limit).all()


def _apply_point_filters(query, intent):
    min_points = intent.get("min_points")
    max_points = intent.get("max_points")
    if min_points is not None:
        query = query.filter(Product.points >= min_points)
    if max_points is not None:
        query = query.filter(Product.points <= max_points)
    return query


def _search_terms(query_text, intent):
    terms = []
    for value in query_text.replace("，", " ").replace(",", " ").split():
        _append_unique(terms, value)
    for value in intent.get("keywords", []):
        _append_unique(terms, value.lstrip("#"))
    for value in intent.get("tags", []):
        _append_unique(terms, value)
        _append_unique(terms, value.lstrip("#"))
    return _expand_terms(terms)[:40]


def _exact_condition_groups(query_text, intent):
    groups = []
    raw_terms = []
    for value in query_text.replace("，", " ").replace(",", " ").split():
        _append_unique(raw_terms, value)
    if intent:
        for value in intent.get("keywords", []):
            _append_unique(raw_terms, value)
        for value in intent.get("tags", []):
            _append_unique(raw_terms, value)

    for term in raw_terms:
        normalized = term.strip().lstrip("#")
        if not normalized:
            continue

        matched_synonym_group = False
        for synonyms in SYNONYM_GROUPS:
            if any(word in normalized or normalized in word for word in synonyms):
                matched_synonym_group = True
                group = tuple(dict.fromkeys(word.lower().lstrip("#") for word in synonyms))
                if group not in groups:
                    groups.append(group)

        if not matched_synonym_group:
            group = (normalized.lower(),)
            if group not in groups:
                groups.append(group)
        if len(groups) >= 8:
            break
    return groups


def _matches_condition_groups(product, condition_groups):
    searchable_text = f"{product.title} {product.description} {product.tags}".lower()
    matched_count = sum(
        1
        for group in condition_groups
        if any(term and term in searchable_text for term in group)
    )

    # AI may return equivalent descriptions as separate terms. Requiring every
    # expansion creates false negatives, while point limits remain strict SQL filters.
    required_count = (
        len(condition_groups)
        if len(condition_groups) <= 2
        else math.ceil(len(condition_groups) * 0.66)
    )
    return matched_count >= required_count


def _score_product(product, query_text, intent, terms):
    score = 0
    title = product.title.lower()
    description = product.description.lower()
    tags = product.tags.lower()
    searchable_text = f"{title} {description} {tags}"

    for keyword in intent.get("keywords", []):
        term = keyword.lower().lstrip("#")
        if not term:
            continue
        if term in title:
            score += 4
        if term in description:
            score += 2
        if term in tags:
            score += 5

    for tag in intent.get("tags", []):
        normalized_tag = tag.lower()
        plain_tag = normalized_tag.lstrip("#")
        if normalized_tag in tags:
            score += 6
        elif plain_tag and plain_tag in tags:
            score += 4

    for term in terms:
        normalized_term = term.lower().lstrip("#")
        if not normalized_term:
            continue
        if normalized_term in title:
            score += 2
        if normalized_term in description:
            score += 1.5
        if normalized_term in tags:
            score += 2.5

    if query_text and query_text.lower() in searchable_text:
        score += 3

    min_points = intent.get("min_points")
    max_points = intent.get("max_points")
    if min_points is not None and product.points >= min_points:
        score += 1
    if max_points is not None and product.points <= max_points:
        score += 2

    score += min(product.view_count, 20) / 20
    return score


def _append_unique(items, value):
    text = str(value).strip()
    if text and text not in items:
        items.append(text)


def _expand_terms(terms):
    expanded = []
    for term in terms:
        _append_unique(expanded, term)
        normalized = term.lstrip("#")
        _append_unique(expanded, normalized)
        for group in SYNONYM_GROUPS:
            if any(word in normalized or normalized in word for word in group):
                for synonym in group:
                    _append_unique(expanded, synonym)
                    _append_unique(expanded, f"#{synonym}")
    return expanded
