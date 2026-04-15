from odoo import _, api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    wishlist_line_id = fields.Many2one("wishlist.line", index=True, copy=False)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _is_mail_simulation_mode(self):
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("cs_baby_wishlist.mail_simulation", "1")
            in ("1", "true", "True")
        )

    def _send_wishlist_update_email(self, wishlist, updated_lines):
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
            line_rows.append(
                "<li><strong>{name}</strong>: comprado {purchased}/{desired} (restante: {remaining})</li>".format(
                    name=line.product_id.display_name,
                    purchased=int(line.quantity_purchased),
                    desired=int(line.quantity_desired),
                    remaining=max(int(line.quantity_desired - line.quantity_purchased), 0),
                )
            )

        body = _(
            "<p>Tu lista de deseos se ha actualizado por una nueva compra.</p>"
            "<p><strong>Lista:</strong> %(list_name)s</p>"
            "<ul>%(lines)s</ul>"
            "<p><strong>Enlace de gestion:</strong> <a href=\"%(manage_url)s\">%(manage_url)s</a></p>"
            "<p><strong>Enlace publico:</strong> <a href=\"%(public_url)s\">%(public_url)s</a></p>"
        ) % {
            "list_name": wishlist.name,
            "lines": "".join(line_rows),
            "manage_url": wishlist.manage_url or "",
            "public_url": wishlist.public_url or "",
        }

        mail = self.env["mail.mail"].sudo().create(
            {
                "subject": _("Actualizacion de tu Baby Wishlist"),
                "email_to": ",".join(recipients),
                "body_html": body,
            }
        )
        if not self._is_mail_simulation_mode():
            mail.send()

    def _cart_update(self, product_id, line_id=None, add_qty=0, set_qty=0, **kwargs):
        wishlist_line_id = kwargs.get("wishlist_line_id")
        if wishlist_line_id:
            wishlist_line = self.env["wishlist.line"].sudo().browse(int(wishlist_line_id))
            if wishlist_line.exists():
                current_in_cart = sum(
                    self.order_line.filtered(
                        lambda l: l.wishlist_line_id.id == wishlist_line.id
                    ).mapped("product_uom_qty")
                )
                max_remaining = max(
                    wishlist_line.quantity_desired
                    - wishlist_line.quantity_purchased
                    - current_in_cart,
                    0,
                )
                add_qty = min(int(float(add_qty or 0)), max_remaining)
                if set_qty:
                    set_qty = min(int(float(set_qty or 0)), max_remaining)
                if add_qty <= 0 and set_qty <= 0:
                    return {"line_id": line_id, "quantity": current_in_cart}
        result = super()._cart_update(
            product_id, line_id=line_id, add_qty=add_qty, set_qty=set_qty, **kwargs
        )
        if wishlist_line_id and result.get("line_id"):
            line = self.env["sale.order.line"].browse(result["line_id"])
            if line and line.order_id == self:
                line.wishlist_line_id = int(wishlist_line_id)
        return result

    def action_confirm(self):
        res = super().action_confirm()
        for order in self:
            wishlist_updates = {}
            for line in order.order_line.filtered(lambda l: l.wishlist_line_id):
                wishlist_line = line.wishlist_line_id.sudo()
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
                self._send_wishlist_update_email(item["wishlist"], item["lines"])
        return res
