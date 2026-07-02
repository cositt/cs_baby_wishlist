from markupsafe import Markup, escape

from odoo import _, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    wishlist_line_id = fields.Many2one("wishlist.line", index=True, copy=False)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    is_wishlist_cart = fields.Boolean(
        string="Carrito de lista de nacimiento",
        copy=False,
        help="Marca el carrito como exclusivo de una lista de nacimiento.",
    )
    wishlist_gift_message = fields.Text(
        string="Dedicatoria para los padres",
        copy=False,
    )
    wishlist_gift_signature = fields.Char(
        string="Firma del comprador",
        copy=False,
    )

    def _is_mail_simulation_mode(self):
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("cs_baby_wishlist.mail_simulation", "1")
            in ("1", "true", "True")
        )

    def _wishlist_exclusive_enabled(self):
        """Toggle desde Odoo (Ajustes -> Tecnico -> Parametros del sistema)."""
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("cs_baby_wishlist.exclusive_cart", "1")
            in ("1", "true", "True")
        )

    def _resolve_wishlist_line(self, order_line, kwargs):
        """Identifica la wishlist.line implicada, venga por kwargs (alta) o por la
        propia linea del carrito (actualizacion de cantidad)."""
        wishlist_line_id = kwargs.get("wishlist_line_id")
        if wishlist_line_id:
            wishlist_line = self.env["wishlist.line"].sudo().browse(int(wishlist_line_id))
            return wishlist_line if wishlist_line.exists() else self.env["wishlist.line"]
        if order_line and order_line.wishlist_line_id:
            return order_line.wishlist_line_id.sudo()
        return self.env["wishlist.line"]

    def _has_non_wishlist_lines(self):
        return bool(self.order_line.filtered(lambda l: not l.wishlist_line_id))

    def _verify_updated_quantity(self, order_line, product_id, new_qty, uom_id, **kwargs):
        """Hook de Odoo 19 para add-to-cart (`_cart_add`) y cambio de cantidad
        (`_cart_update_line_quantity`). Sustituye al desaparecido `_cart_update`.

        - Feature C: aisla el carrito de la lista (bloqueo con aviso, toggleable).
        - Cap de cantidad a lo que falta por comprar en la lista.
        - Marca `is_wishlist_cart` en cuanto entra el primer item de lista.
        """
        wishlist_line = self._resolve_wishlist_line(order_line, kwargs)

        if self._wishlist_exclusive_enabled():
            if self.is_wishlist_cart and not wishlist_line:
                return 0, _(
                    "Este carrito es exclusivo para la lista de nacimiento. Finalizalo "
                    "primero; para compras personales usa un carrito nuevo despues."
                )
            if not self.is_wishlist_cart and wishlist_line and self._has_non_wishlist_lines():
                return 0, _(
                    "Tienes productos personales en el carrito. Finaliza esa compra y usa "
                    "un carrito nuevo para el item de la lista de nacimiento."
                )

        new_qty, warning = super()._verify_updated_quantity(
            order_line, product_id, new_qty, uom_id, **kwargs
        )

        if wishlist_line:
            remaining = max(
                int(wishlist_line.quantity_desired - wishlist_line.quantity_purchased), 0
            )
            if new_qty > remaining:
                new_qty = remaining
                warning = warning or _(
                    "Solo puedes comprar las unidades que faltan en la lista de nacimiento."
                )
            if new_qty > 0 and not self.is_wishlist_cart:
                self.is_wishlist_cart = True

        return new_qty, warning

    def _send_wishlist_update_email(self, wishlist, updated_lines, gift_message=None, gift_signature=None):
        recipients = []
        if wishlist.customer_id.email:
            recipients.append(wishlist.customer_id.email)
        if wishlist.co_parent_id.email:
            recipients.append(wishlist.co_parent_id.email)
        recipients = list(dict.fromkeys(recipients))
        if not recipients or not updated_lines:
            return

        line_rows = []
        for line in updated_lines:
            line_rows.append(Markup(
                "<li><strong>{name}</strong>: comprado {purchased}/{desired} (restante: {remaining})</li>"
            ).format(
                name=escape(line.product_id.display_name),
                purchased=int(line.quantity_purchased),
                desired=int(line.quantity_desired),
                remaining=max(int(line.quantity_desired - line.quantity_purchased), 0),
            ))

        gift_block = Markup("")
        if gift_message or gift_signature:
            gift_parts = [Markup("<hr/><p><strong>Dedicatoria del comprador:</strong></p>")]
            if gift_message:
                gift_parts.append(
                    Markup("<blockquote>{msg}</blockquote>").format(msg=escape(gift_message))
                )
            if gift_signature:
                gift_parts.append(
                    Markup("<p><em>— {sign}</em></p>").format(sign=escape(gift_signature))
                )
            gift_block = Markup("".join(str(p) for p in gift_parts))

        body = Markup(
            "<p>Tu lista de deseos se ha actualizado por una nueva compra.</p>"
            "<p><strong>Lista:</strong> {list_name}</p>"
            "<ul>{lines}</ul>"
            "{gift_block}"
            "<p><strong>Enlace de gestion:</strong> <a href=\"{manage_url}\">{manage_url}</a></p>"
            "<p><strong>Enlace publico:</strong> <a href=\"{public_url}\">{public_url}</a></p>"
        ).format(
            list_name=escape(wishlist.name),
            lines=Markup("".join(str(r) for r in line_rows)),
            gift_block=gift_block,
            manage_url=escape(wishlist.manage_url or ""),
            public_url=escape(wishlist.public_url or ""),
        )

        mail = self.env["mail.mail"].sudo().create(
            {
                "subject": _("Actualizacion de tu Baby Wishlist"),
                "email_to": ",".join(recipients),
                "body_html": body,
            }
        )
        if not self._is_mail_simulation_mode():
            mail.send()

    def action_confirm(self):
        res = super().action_confirm()
        wishlist_line_ids = (
            self.order_line.filtered(lambda l: l.wishlist_line_id).mapped("wishlist_line_id").ids
        )
        if wishlist_line_ids:
            # Lock rows first so concurrent confirmations on the same wishlist line
            # serialize instead of both reading a stale quantity_purchased.
            self.env.cr.execute(
                "SELECT id FROM wishlist_line WHERE id = ANY(%s) FOR UPDATE",
                (wishlist_line_ids,),
            )
        for order in self:
            wishlist_updates = {}
            for line in order.order_line.filtered(lambda l: l.wishlist_line_id):
                wishlist_line = line.wishlist_line_id.sudo()
                wishlist_line.invalidate_recordset(["quantity_purchased"])
                remaining = wishlist_line.quantity_desired - wishlist_line.quantity_purchased
                if remaining <= 0:
                    continue
                qty_to_add = min(line.product_uom_qty, remaining)
                if qty_to_add > 0:
                    qty_to_add = int(qty_to_add)
                    wishlist_line.write(
                        {"quantity_purchased": wishlist_line.quantity_purchased + qty_to_add}
                    )
                    wishlist = wishlist_line.wishlist_id
                    wishlist_updates.setdefault(wishlist.id, {"wishlist": wishlist, "lines": []})
                    wishlist_updates[wishlist.id]["lines"].append(wishlist_line)
            for item in wishlist_updates.values():
                order._send_wishlist_update_email(
                    item["wishlist"],
                    item["lines"],
                    gift_message=order.wishlist_gift_message,
                    gift_signature=order.wishlist_gift_signature,
                )
        return res
