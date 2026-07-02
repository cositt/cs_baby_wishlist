{
    "name": "Baby Wishlist",
    "version": "19.0.1.0.0",
    "summary": "Gestion de listas de nacimiento con compra publica",
    "category": "Sales",
    "author": "Custom",
    "license": "LGPL-3",
    "images": ["static/description/icon.png"],
    "depends": ["base", "product", "sale", "website", "website_sale", "website_sale_wishlist"],
    "data": [
        "security/groups.xml",
        "security/ir.model.access.csv",
        "security/ir_rule.xml",
        "views/wishlist_views.xml",
        "views/partner_views.xml",
        "views/disable_native_wishlist_views.xml",
        "views/templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "cs_baby_wishlist/static/src/css/cs_baby_wishlist.css",
            "cs_baby_wishlist/static/src/js/cs_baby_wishlist.js",
        ],
    },
    "application": True,
    "installable": True,
}
