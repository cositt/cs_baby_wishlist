from urllib.parse import urlencode

from odoo import _, http
from odoo.http import request


class WishlistController(http.Controller):
    @staticmethod
    def _to_int_qty(raw_qty, default=1):
        try:
            qty = int(float(raw_qty))
        except (TypeError, ValueError):
            qty = default
        return max(qty, 1)

    @http.route("/my/baby-wishlist", type="http", auth="user", website=True, sitemap=False)
    def wishlist_my_shortcut(self, **kwargs):
        return request.redirect("/baby-wishlist/my")

    @http.route("/my/baby-wishlist/new", type="http", auth="user", website=True, sitemap=False)
    def wishlist_new_shortcut(self, **kwargs):
        return request.redirect("/baby-wishlist")

    def _session_cart(self):
        cart = request.session.get("baby_wishlist_cart", {})
        if not isinstance(cart, dict):
            cart = {}
        normalized = {}
        for key, value in cart.items():
            qty = self._to_int_qty(value)
            if qty > 0:
                normalized[str(key)] = qty
        return normalized

    def _save_session_cart(self, cart):
        request.session["baby_wishlist_cart"] = {
            str(k): self._to_int_qty(v) for k, v in cart.items() if self._to_int_qty(v) > 0
        }

    def _retail_pricelists(self):
        """Devuelve (regular, sale) segun la config de la instancia WooCommerce.

        product.list_price es un placeholder (1.00) importado de Woo; el precio real
        vive en la pricelist "regular" (woo_pricelist_id), con descuento opcional en la
        "sale" (woo_extra_pricelist_id). Se usa la regular para TODOS los visitantes
        (portal/anonimo resuelven la pricelist de venta -> 0.00, por eso no se usa la
        pricelist de sesion). Fallback a la pricelist de sesion si no hay instancia Woo.
        """
        empty = request.env["product.pricelist"].sudo()
        regular = empty
        sale = empty
        if "woo.instance.ept" in request.env:
            instance = request.env["woo.instance.ept"].sudo().search([], limit=1)
            if instance:
                regular = instance.woo_pricelist_id
                sale = instance.woo_extra_pricelist_id
        if not regular:
            regular = request.website._get_and_cache_current_pricelist()
        return regular, sale

    def _price_map(self, products):
        """Precio real por producto: pricelist regular de Woo, con descuento sale si aplica."""
        regular, sale = self._retail_pricelists()
        price_map = {}
        for product in products:
            base = regular._get_product_price(product, 1.0) if regular else product.list_price
            if sale:
                promo = sale._get_product_price(product, 1.0)
                if 0.0 < promo < base:
                    base = promo
            price_map[product.id] = base
        return price_map

    def _get_active_manage_wishlist(self):
        manage_token = request.session.get("baby_wishlist_manage_token")
        if not manage_token:
            return request.env["wishlist.list"]
        return request.env["wishlist.list"].sudo().search([("manage_token", "=", manage_token)], limit=1)

    @http.route("/baby-wishlist", type="http", auth="user", website=True, sitemap=False)
    def wishlist_builder(self, search=None, **kwargs):
        domain = [("sale_ok", "=", True), ("active", "=", True), ("product_tmpl_id.is_published", "=", True)]
        if search:
            domain.append(("name", "ilike", search))
        products = request.env["product.product"].sudo().search(domain, limit=120)
        cart = self._session_cart()
        cart_lines = []
        product_map = {str(p.id): p for p in products}
        for product_id, qty in cart.items():
            product = product_map.get(str(product_id)) or request.env["product.product"].sudo().browse(int(product_id))
            if product.exists():
                cart_lines.append({"product": product, "qty": qty})
        return request.render(
            "cs_baby_wishlist.wishlist_builder_page",
            {
                "products": products,
                "cart_lines": cart_lines,
                "price_map": self._price_map(products),
                "search": search or "",
                "error": kwargs.get("error"),
                "success": kwargs.get("success"),
            },
        )

    @http.route("/baby-wishlist/cart/add", type="http", auth="user", methods=["POST"], website=True, sitemap=False)
    def wishlist_cart_add(self, product_id=None, qty=1, **kwargs):
        product = request.env["product.product"].sudo().browse(int(product_id or 0))
        if not product.exists() or not product.sale_ok or not product.product_tmpl_id.is_published:
            return request.redirect("/baby-wishlist?" + urlencode({"error": _("Producto no valido.")}))
        cart = self._session_cart()
        new_qty = cart.get(str(product.id), 0) + self._to_int_qty(qty)
        cart[str(product.id)] = new_qty
        self._save_session_cart(cart)
        return request.redirect("/baby-wishlist")

    @http.route(
        "/baby-wishlist/cart/remove", type="http", auth="user", methods=["POST"], website=True, sitemap=False
    )
    def wishlist_cart_remove(self, product_id=None, **kwargs):
        cart = self._session_cart()
        if product_id and str(product_id) in cart:
            cart.pop(str(product_id))
            self._save_session_cart(cart)
        return request.redirect("/baby-wishlist")

    @http.route("/baby-wishlist/create", type="http", auth="user", methods=["POST"], website=True, sitemap=False)
    def wishlist_create(self, name=None, event_date=None, notes=None, co_parent_email=None, **kwargs):
        partner = request.env.user.partner_id
        cart = self._session_cart()
        if not cart:
            return request.redirect("/baby-wishlist?" + urlencode({"error": _("Agrega productos antes de crear la lista.")}))
        if not name:
            return request.redirect("/baby-wishlist?" + urlencode({"error": _("El nombre de la lista es obligatorio.")}))

        co_parent = False
        if co_parent_email:
            co_parent = (
                request.env["res.partner"]
                .sudo()
                .search([("email", "=ilike", co_parent_email.strip()), ("user_ids", "!=", False)], limit=1)
            )
            if not co_parent:
                return request.redirect(
                    "/baby-wishlist?" + urlencode({"error": _("El co-parent debe estar registrado en el sitio.")})
                )

        wishlist = request.env["wishlist.list"].sudo().create(
            {
                "name": name.strip(),
                "customer_id": partner.id,
                "co_parent_id": co_parent.id if co_parent else False,
                "event_date": event_date or False,
                "notes": notes or False,
                "state": "active",
            }
        )
        for product_id, qty in cart.items():
            request.env["wishlist.line"].sudo().create(
                {
                    "wishlist_id": wishlist.id,
                    "product_id": int(product_id),
                    "quantity_desired": int(qty),
                    "priority": "medium",
                }
            )
        self._save_session_cart({})

        if request.env.user.email:
            body = _(
                "<p>Tu lista de nacimiento se ha creado correctamente.</p>"
                "<p><strong>Lista:</strong> %(name)s</p>"
                "<p><strong>Enlace para compartir:</strong> <a href=\"%(url)s\">%(url)s</a></p>"
                "<p><strong>Enlace para gestionar tu lista:</strong> <a href=\"%(manage_url)s\">%(manage_url)s</a></p>"
            ) % {"name": wishlist.name, "url": wishlist.public_url, "manage_url": wishlist.manage_url}
            mail = request.env["mail.mail"].sudo().create(
                {
                    "subject": _("Tu Baby Wishlist está lista"),
                    "email_to": request.env.user.email,
                    "body_html": body,
                }
            )
            simulation_mode = (
                request.env["ir.config_parameter"].sudo().get_param(
                    "cs_baby_wishlist.mail_simulation", "1"
                )
                in ("1", "true", "True")
            )
            if not simulation_mode:
                mail.send()

        return request.redirect("/baby-wishlist/my?success=1")

    def _check_manage_access(self, wishlist):
        partner_id = request.env.user.partner_id.id
        return wishlist and partner_id in (wishlist.customer_id.id, wishlist.co_parent_id.id)

    @http.route("/wishlist/manage/<string:manage_token>", type="http", auth="user", website=True, sitemap=False)
    def wishlist_manage_page(self, manage_token, search=None, **kwargs):
        wishlist = request.env["wishlist.list"].sudo().search([("manage_token", "=", manage_token)], limit=1)
        if not wishlist:
            return request.not_found()
        if not self._check_manage_access(wishlist):
            return request.redirect("/baby-wishlist/my?" + urlencode({"error": _("No tienes acceso a esta lista.")}))
        request.session["baby_wishlist_manage_token"] = wishlist.manage_token
        products = request.env["product.product"]
        if search:
            products = request.env["product.product"].sudo().search(
                [
                    ("sale_ok", "=", True),
                    ("active", "=", True),
                    ("product_tmpl_id.is_published", "=", True),
                    ("name", "ilike", search),
                ],
                limit=40,
            )
        return request.render(
            "cs_baby_wishlist.wishlist_manage_page",
            {
                "wishlist": wishlist,
                "products": products,
                "search": search or "",
                "error": kwargs.get("error"),
                "success": kwargs.get("success"),
            },
        )

    @http.route("/wishlist/manage/<string:manage_token>/catalog", type="http", auth="user", website=True, sitemap=False)
    def wishlist_manage_catalog(self, manage_token, **kwargs):
        wishlist = request.env["wishlist.list"].sudo().search([("manage_token", "=", manage_token)], limit=1)
        if not wishlist:
            return request.not_found()
        if not self._check_manage_access(wishlist):
            return request.redirect("/baby-wishlist/my?" + urlencode({"error": _("No tienes acceso a esta lista.")}))
        request.session["baby_wishlist_manage_token"] = wishlist.manage_token
        return request.redirect("/shop")

    @http.route("/wishlist/catalog/add", type="http", auth="user", methods=["POST"], website=True, sitemap=False)
    def wishlist_catalog_add(self, product_id=None, qty=1, wishlist_id=None, next_url=None, **kwargs):
        if wishlist_id:
            wishlist = request.env["wishlist.list"].sudo().search(
                [
                    ("id", "=", int(wishlist_id)),
                    "|",
                    ("customer_id", "=", request.env.user.partner_id.id),
                    ("co_parent_id", "=", request.env.user.partner_id.id),
                ],
                limit=1,
            )
        else:
            wishlist = self._get_active_manage_wishlist()
        if not wishlist:
            return request.redirect("/baby-wishlist/my?error=Selecciona+una+lista+de+deseos")
        if wishlist.state == "closed":
            return request.redirect(f"/wishlist/manage/{wishlist.manage_token}?error=Lista+cerrada")
        product = request.env["product.product"].sudo().browse(int(product_id or 0))
        if not product.exists() or not product.sale_ok or not product.product_tmpl_id.is_published:
            return request.redirect(f"/wishlist/manage/{wishlist.manage_token}?error=Producto+no+valido")
        qty = self._to_int_qty(qty)
        line = request.env["wishlist.line"].sudo().search(
            [("wishlist_id", "=", wishlist.id), ("product_id", "=", product.id)], limit=1
        )
        if line:
            line.write({"quantity_desired": line.quantity_desired + qty})
        else:
            request.env["wishlist.line"].sudo().create(
                {"wishlist_id": wishlist.id, "product_id": product.id, "quantity_desired": qty}
            )
        return request.redirect(f"/wishlist/manage/{wishlist.manage_token}?success=1")

    @http.route(
        "/wishlist/manage/<string:manage_token>/add", type="http", auth="user", methods=["POST"], website=True, sitemap=False
    )
    def wishlist_manage_add_product(self, manage_token, product_id=None, qty=1, **kwargs):
        wishlist = request.env["wishlist.list"].sudo().search([("manage_token", "=", manage_token)], limit=1)
        if not self._check_manage_access(wishlist):
            return request.redirect("/baby-wishlist/my?" + urlencode({"error": _("No tienes acceso a esta lista.")}))
        if not wishlist or wishlist.state == "closed":
            return request.redirect(f"/wishlist/manage/{manage_token}?error=Lista+cerrada")
        product = request.env["product.product"].sudo().browse(int(product_id or 0))
        if not product.exists() or not product.sale_ok or not product.product_tmpl_id.is_published:
            return request.redirect(f"/wishlist/manage/{manage_token}?error=Producto+no+valido")
        qty = self._to_int_qty(qty)
        line = request.env["wishlist.line"].sudo().search(
            [("wishlist_id", "=", wishlist.id), ("product_id", "=", product.id)], limit=1
        )
        if line:
            line.write({"quantity_desired": line.quantity_desired + qty})
        else:
            request.env["wishlist.line"].sudo().create(
                {"wishlist_id": wishlist.id, "product_id": product.id, "quantity_desired": qty}
            )
        return request.redirect(f"/wishlist/manage/{manage_token}?success=1")

    @http.route(
        "/wishlist/manage/<string:manage_token>/remove/<int:line_id>",
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
        sitemap=False,
    )
    def wishlist_manage_remove_line(self, manage_token, line_id, **kwargs):
        wishlist = request.env["wishlist.list"].sudo().search([("manage_token", "=", manage_token)], limit=1)
        if not self._check_manage_access(wishlist):
            return request.redirect("/baby-wishlist/my?" + urlencode({"error": _("No tienes acceso a esta lista.")}))
        if not wishlist or wishlist.state == "closed":
            return request.redirect(f"/wishlist/manage/{manage_token}?error=Lista+cerrada")
        line = request.env["wishlist.line"].sudo().search(
            [("id", "=", line_id), ("wishlist_id", "=", wishlist.id)], limit=1
        )
        if line:
            line.unlink()
        return request.redirect(f"/wishlist/manage/{manage_token}?success=1")

    @http.route("/baby-wishlist/my", type="http", auth="user", website=True, sitemap=False)
    def wishlist_my(self, **kwargs):
        partner_id = request.env.user.partner_id.id
        wishlists = (
            request.env["wishlist.list"]
            .sudo()
            .search(["|", ("customer_id", "=", partner_id), ("co_parent_id", "=", partner_id)], order="id desc")
        )
        return request.render(
            "cs_baby_wishlist.wishlist_my_page",
            {"wishlists": wishlists, "success": kwargs.get("success")},
        )

    @http.route("/wishlist/<string:token>", type="http", auth="public", website=True, sitemap=False)
    def wishlist_public_page(self, token, **kwargs):
        wishlist = request.env["wishlist.list"].sudo().search([("token", "=", token)], limit=1)
        if not wishlist:
            return request.not_found()
        lines = wishlist.line_ids
        product_price_map = self._price_map(lines.mapped("product_id"))
        line_price_map = {line.id: product_price_map.get(line.product_id.id, 0.0) for line in lines}
        return request.render(
            "cs_baby_wishlist.wishlist_public_page",
            {"wishlist": wishlist, "lines": lines, "line_price_map": line_price_map},
        )

    @http.route(
        "/wishlist/<string:token>/buy/<int:line_id>",
        type="http",
        auth="public",
        website=True,
        methods=["POST"],
        sitemap=False,
    )
    def wishlist_buy(self, token, line_id, qty=1, continue_shopping="0", **kwargs):
        wishlist = request.env["wishlist.list"].sudo().search([("token", "=", token)], limit=1)
        if not wishlist or wishlist.state != "active":
            return request.redirect(f"/wishlist/{token}")

        line = request.env["wishlist.line"].sudo().search(
            [("id", "=", line_id), ("wishlist_id", "=", wishlist.id)],
            limit=1,
        )
        if not line:
            return request.redirect(f"/wishlist/{token}")

        remaining = line.remaining_qty
        if remaining <= 0:
            return request.redirect(f"/wishlist/{token}")

        requested_qty = self._to_int_qty(qty)

        order = request.cart or request.website._create_cart()
        current_qty = sum(
            order.order_line.filtered(lambda l: l.wishlist_line_id.id == line.id).mapped("product_uom_qty")
        )
        max_addable = max(int(remaining - current_qty), 0)
        qty_to_add = min(requested_qty, max_addable)
        if qty_to_add <= 0:
            return request.redirect(f"/wishlist/{token}")

        values = order.with_context(skip_cart_verification=True)._cart_add(
            product_id=line.product_id.id,
            quantity=qty_to_add,
            wishlist_line_id=line.id,
        )
        line_id_created = values.get("line_id")
        if line_id_created:
            request.env["sale.order.line"].sudo().browse(line_id_created).write(
                {"wishlist_line_id": line.id}
            )
        if str(continue_shopping) == "1":
            return request.redirect(f"/wishlist/{token}")
        return request.redirect("/shop/cart")
