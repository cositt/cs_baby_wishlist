import uuid

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class WishlistList(models.Model):
    _name = "wishlist.list"
    _description = "Baby Wishlist"
    _order = "id desc"

    active = fields.Boolean(default=True)
    name = fields.Char(required=True)
    customer_id = fields.Many2one("res.partner", required=True)
    co_parent_id = fields.Many2one("res.partner")
    token = fields.Char(required=True, copy=False, readonly=True, index=True)
    manage_token = fields.Char(copy=False, readonly=True, index=True)
    public_url = fields.Char(compute="_compute_public_url")
    manage_url = fields.Char(compute="_compute_manage_url")
    state = fields.Selection(
        [("draft", "Draft"), ("active", "Active"), ("closed", "Closed")],
        default="draft",
        required=True,
    )
    event_date = fields.Date()
    notes = fields.Text()
    line_ids = fields.One2many("wishlist.line", "wishlist_id", string="Products")

    _token_unique = models.Constraint(
        "UNIQUE(token)",
        "Wishlist token must be unique.",
    )
    _manage_token_unique = models.Constraint(
        "UNIQUE(manage_token)",
        "Wishlist manage token must be unique.",
    )

    @api.depends("token")
    def _compute_public_url(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        for rec in self:
            rec.public_url = f"{base_url}/wishlist/{rec.token}" if rec.token else False

    @api.depends("manage_token")
    def _compute_manage_url(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        for rec in self:
            rec.manage_url = f"{base_url}/wishlist/manage/{rec.manage_token}" if rec.manage_token else False

    @api.model
    def _generate_token(self):
        return uuid.uuid4().hex

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("token"):
                vals["token"] = uuid.uuid4().hex
            if not vals.get("manage_token"):
                vals["manage_token"] = uuid.uuid4().hex
        return super().create(vals_list)

    def write(self, vals):
        if any(rec.state == "closed" for rec in self):
            allowed = {"state", "active"}
            if not set(vals).issubset(allowed):
                raise UserError(_("Closed wishlists cannot be edited."))
        return super().write(vals)

    def unlink(self):
        if any(rec.state == "closed" for rec in self):
            raise UserError(_("Closed wishlists cannot be deleted."))
        return super().unlink()

    def action_set_draft(self):
        self.write({"state": "draft"})

    def action_set_active(self):
        self.write({"state": "active"})

    def action_set_closed(self):
        self.write({"state": "closed"})


class WishlistLine(models.Model):
    _name = "wishlist.line"
    _description = "Baby Wishlist Line"
    _order = "priority desc, id"

    wishlist_id = fields.Many2one("wishlist.list", required=True, ondelete="cascade")
    product_id = fields.Many2one("product.product", required=True)
    quantity_desired = fields.Integer(required=True, default=1)
    quantity_purchased = fields.Integer(default=0)
    priority = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High")],
        default="medium",
        required=True,
    )
    notes = fields.Char()
    is_fulfilled = fields.Boolean(compute="_compute_is_fulfilled", store=True)
    remaining_qty = fields.Integer(compute="_compute_remaining_qty", store=True)
    product_price = fields.Float(related="product_id.list_price", store=False)

    @api.depends("quantity_desired", "quantity_purchased")
    def _compute_is_fulfilled(self):
        for rec in self:
            rec.is_fulfilled = rec.quantity_purchased >= rec.quantity_desired

    @api.depends("quantity_desired", "quantity_purchased")
    def _compute_remaining_qty(self):
        for rec in self:
            rec.remaining_qty = max(rec.quantity_desired - rec.quantity_purchased, 0)

    @api.constrains("quantity_desired", "quantity_purchased")
    def _check_quantities(self):
        for rec in self:
            if rec.quantity_desired <= 0:
                raise ValidationError(_("Desired quantity must be greater than zero."))
            if rec.quantity_purchased < 0:
                raise ValidationError(_("Purchased quantity cannot be negative."))
            if rec.quantity_purchased > rec.quantity_desired:
                raise ValidationError(_("Purchased quantity cannot exceed desired quantity."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            wishlist = self.env["wishlist.list"].browse(vals.get("wishlist_id"))
            if wishlist and wishlist.state == "closed":
                raise UserError(_("Cannot add lines to a closed wishlist."))
        return super().create(vals_list)

    def write(self, vals):
        if any(rec.wishlist_id.state == "closed" for rec in self):
            raise UserError(_("Cannot edit lines from a closed wishlist."))
        return super().write(vals)

    def unlink(self):
        if any(rec.wishlist_id.state == "closed" for rec in self):
            raise UserError(_("Cannot delete lines from a closed wishlist."))
        return super().unlink()
