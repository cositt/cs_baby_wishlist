from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    wishlist_ids = fields.One2many("wishlist.list", "customer_id", string="Wishlists")
    wishlist_count = fields.Integer(compute="_compute_wishlist_count")

    def _compute_wishlist_count(self):
        grouped = self.env["wishlist.list"]._read_group(
            [("customer_id", "in", self.ids)],
            ["customer_id"],
            ["__count"],
        )
        counts = {customer.id: count for customer, count in grouped}
        for partner in self:
            partner.wishlist_count = counts.get(partner.id, 0)

    def action_view_wishlists(self):
        self.ensure_one()
        action = self.env.ref("cs_baby_wishlist.action_wishlist_list").read()[0]
        action["domain"] = [("customer_id", "=", self.id)]
        action["context"] = {"default_customer_id": self.id}
        return action
