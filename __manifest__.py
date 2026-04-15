{
    "name": "Baby Wishlist",
    "version": "19.0.1.0.0",
    "summary": "Gestion de listas de nacimiento con compra publica",
    "category": "Sales",
    "author": "Custom",
    "license": "LGPL-3",
    "images": ["static/description/icon.png"],
    "depends": ["base", "product", "sale", "website", "website_sale"],
    "data": [
        "security/ir.model.access.csv",
        "views/wishlist_views.xml",
        "views/partner_views.xml",
        "views/disable_native_wishlist_views.xml",
        "views/templates.xml",
    ],
    "application": True,
    "installable": True,
}
