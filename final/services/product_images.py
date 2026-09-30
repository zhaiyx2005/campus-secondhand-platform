"""Resolve local image references without replacing users' original records."""

import os

from flask import current_app, url_for


def product_image_url(value):
    """Show a neutral placeholder when an upload is absent or unsafe."""
    placeholder = url_for("static", filename="img/product-placeholder.svg")
    if not isinstance(value, str):
        return placeholder
    roots = (
        ("/uploads/", current_app.config["UPLOAD_FOLDER"]),
        (current_app.static_url_path + "/", current_app.static_folder),
    )
    for prefix, root in roots:
        if not value.startswith(prefix):
            continue
        root = os.path.realpath(root)
        path = os.path.realpath(os.path.join(root, value[len(prefix):]))
        try:
            within_root = os.path.commonpath([root, path]) == root
        except ValueError:
            within_root = False
        return value if within_root and os.path.isfile(path) else placeholder
    return placeholder
