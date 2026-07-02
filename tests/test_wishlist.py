from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestWishlistList(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Test Parent", "email": "parent@test.com"})
        cls.partner2 = cls.env["res.partner"].create({"name": "Test Co-Parent", "email": "coparent@test.com"})
        cls.product = cls.env["product.product"].create({"name": "Baby Stroller", "list_price": 200.0, "sale_ok": True})

    def _make_wishlist(self, state="draft", co_parent=False):
        vals = {
            "name": "Lista de nacimiento",
            "customer_id": self.partner.id,
            "state": state,
        }
        if co_parent:
            vals["co_parent_id"] = self.partner2.id
        return self.env["wishlist.list"].create(vals)

    def test_token_generation(self):
        wishlist = self._make_wishlist()
        self.assertTrue(wishlist.token, "Token must be generated on create")
        self.assertTrue(wishlist.manage_token, "Manage token must be generated on create")
        self.assertNotEqual(wishlist.token, wishlist.manage_token)
        self.assertEqual(len(wishlist.token), 32)

    def test_token_uniqueness_constraint(self):
        w1 = self._make_wishlist()
        w2 = self._make_wishlist()
        self.assertNotEqual(w1.token, w2.token)
        self.assertNotEqual(w1.manage_token, w2.manage_token)

    def test_state_transitions(self):
        wishlist = self._make_wishlist(state="draft")
        self.assertEqual(wishlist.state, "draft")
        wishlist.action_set_active()
        self.assertEqual(wishlist.state, "active")
        wishlist.action_set_closed()
        self.assertEqual(wishlist.state, "closed")
        wishlist.action_set_draft()
        self.assertEqual(wishlist.state, "draft")

    def test_closed_wishlist_blocks_edit(self):
        wishlist = self._make_wishlist(state="active")
        wishlist.action_set_closed()
        with self.assertRaises(UserError):
            wishlist.write({"name": "Nuevo nombre"})

    def test_closed_wishlist_blocks_delete(self):
        wishlist = self._make_wishlist(state="active")
        wishlist.action_set_closed()
        with self.assertRaises(UserError):
            wishlist.unlink()

    def test_public_url_computed(self):
        wishlist = self._make_wishlist()
        self.assertIn(wishlist.token, wishlist.public_url)

    def test_manage_url_computed(self):
        wishlist = self._make_wishlist()
        self.assertIn(wishlist.manage_token, wishlist.manage_url)

    def test_coparent_set(self):
        wishlist = self._make_wishlist(co_parent=True)
        self.assertEqual(wishlist.co_parent_id, self.partner2)

    def test_wishlist_count_on_partner(self):
        self._make_wishlist()
        self._make_wishlist()
        self.partner._compute_wishlist_count()
        self.assertEqual(self.partner.wishlist_count, 2)


class TestWishlistLine(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Test Parent"})
        cls.product = cls.env["product.product"].create({"name": "Baby Monitor", "list_price": 80.0, "sale_ok": True})
        cls.wishlist = cls.env["wishlist.list"].create({
            "name": "Test Lista",
            "customer_id": cls.partner.id,
            "state": "active",
        })

    def _make_line(self, desired=3, purchased=0):
        return self.env["wishlist.line"].create({
            "wishlist_id": self.wishlist.id,
            "product_id": self.product.id,
            "quantity_desired": desired,
            "quantity_purchased": purchased,
        })

    def test_remaining_qty_compute(self):
        line = self._make_line(desired=3, purchased=1)
        self.assertEqual(line.remaining_qty, 2)

    def test_is_fulfilled_compute(self):
        line = self._make_line(desired=2, purchased=2)
        self.assertTrue(line.is_fulfilled)

    def test_is_not_fulfilled(self):
        line = self._make_line(desired=2, purchased=1)
        self.assertFalse(line.is_fulfilled)

    def test_quantity_desired_must_be_positive(self):
        with self.assertRaises(ValidationError):
            self._make_line(desired=0)

    def test_purchased_cannot_exceed_desired(self):
        with self.assertRaises(ValidationError):
            self._make_line(desired=2, purchased=5)

    def test_purchased_cannot_be_negative(self):
        with self.assertRaises(ValidationError):
            self._make_line(desired=2, purchased=-1)

    def test_cannot_add_line_to_closed_wishlist(self):
        self.wishlist.action_set_closed()
        with self.assertRaises(UserError):
            self._make_line()

    def test_cannot_edit_line_on_closed_wishlist(self):
        line = self._make_line()
        self.wishlist.action_set_closed()
        with self.assertRaises(UserError):
            line.write({"quantity_desired": 5})

    def test_cannot_delete_line_on_closed_wishlist(self):
        line = self._make_line()
        self.wishlist.action_set_closed()
        with self.assertRaises(UserError):
            line.unlink()


class TestWishlistExclusiveCart(TransactionCase):
    """Feature C: el carrito de una lista solo admite items de esa lista."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Buyer", "email": "buyer@test.com"})
        cls.list_product = cls.env["product.product"].create(
            {"name": "List Product", "list_price": 50.0, "sale_ok": True}
        )
        cls.shop_product = cls.env["product.product"].create(
            {"name": "Shop Product", "list_price": 30.0, "sale_ok": True}
        )
        cls.wishlist = cls.env["wishlist.list"].create(
            {"name": "Lista", "customer_id": cls.partner.id, "state": "active"}
        )
        cls.line = cls.env["wishlist.line"].create(
            {
                "wishlist_id": cls.wishlist.id,
                "product_id": cls.list_product.id,
                "quantity_desired": 3,
                "quantity_purchased": 0,
            }
        )

    def setUp(self):
        super().setUp()
        # Enforcement activo por defecto en cada test.
        self.env["ir.config_parameter"].sudo().set_param("cs_baby_wishlist.exclusive_cart", "1")

    def _order(self):
        return self.env["sale.order"].create({"partner_id": self.partner.id})

    def _empty_line(self):
        return self.env["sale.order.line"]

    def _add_normal_line(self, order, product):
        order.write(
            {"order_line": [(0, 0, {"product_id": product.id, "product_uom_qty": 1})]}
        )
        return order.order_line[-1:]

    def test_wishlist_item_marks_cart(self):
        order = self._order()
        qty, warning = order._verify_updated_quantity(
            self._empty_line(),
            self.list_product.id,
            2,
            self.list_product.uom_id.id,
            wishlist_line_id=self.line.id,
        )
        self.assertEqual(qty, 2)
        self.assertFalse(warning)
        self.assertTrue(order.is_wishlist_cart)

    def test_normal_product_rejected_in_wishlist_cart(self):
        order = self._order()
        order.is_wishlist_cart = True
        qty, warning = order._verify_updated_quantity(
            self._empty_line(),
            self.shop_product.id,
            1,
            self.shop_product.uom_id.id,
        )
        self.assertEqual(qty, 0)
        self.assertTrue(warning)

    def test_wishlist_item_rejected_in_normal_cart(self):
        order = self._order()
        self._add_normal_line(order, self.shop_product)
        qty, warning = order._verify_updated_quantity(
            self._empty_line(),
            self.list_product.id,
            1,
            self.list_product.uom_id.id,
            wishlist_line_id=self.line.id,
        )
        self.assertEqual(qty, 0)
        self.assertTrue(warning)

    def test_qty_capped_to_remaining(self):
        order = self._order()
        qty, _warning = order._verify_updated_quantity(
            self._empty_line(),
            self.list_product.id,
            10,
            self.list_product.uom_id.id,
            wishlist_line_id=self.line.id,
        )
        self.assertEqual(qty, 3)

    def test_toggle_off_allows_mixing(self):
        self.env["ir.config_parameter"].sudo().set_param("cs_baby_wishlist.exclusive_cart", "0")
        order = self._order()
        order.is_wishlist_cart = True
        qty, warning = order._verify_updated_quantity(
            self._empty_line(),
            self.shop_product.id,
            1,
            self.shop_product.uom_id.id,
        )
        self.assertEqual(qty, 1)
        self.assertFalse(warning)


class TestWishlistGift(TransactionCase):
    """Feature A: dedicatoria + firma por compra, incluida en el email a los padres."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Parent", "email": "gift-parent@test.com"}
        )
        cls.buyer = cls.env["res.partner"].create({"name": "Buyer", "email": "gift-buyer@test.com"})
        cls.product = cls.env["product.product"].create(
            {"name": "Gift Product", "list_price": 40.0, "sale_ok": True}
        )
        cls.wishlist = cls.env["wishlist.list"].create(
            {"name": "Lista Regalo", "customer_id": cls.partner.id, "state": "active"}
        )
        cls.line = cls.env["wishlist.line"].create(
            {
                "wishlist_id": cls.wishlist.id,
                "product_id": cls.product.id,
                "quantity_desired": 2,
                "quantity_purchased": 1,
            }
        )

    def test_gift_fields_persist_on_order(self):
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        order.write(
            {
                "is_wishlist_cart": True,
                "wishlist_gift_message": "Con mucho cariño para el bebé",
                "wishlist_gift_signature": "Tío Juan",
            }
        )
        self.assertEqual(order.wishlist_gift_message, "Con mucho cariño para el bebé")
        self.assertEqual(order.wishlist_gift_signature, "Tío Juan")

    def test_gift_included_in_email(self):
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        before = self.env["mail.mail"].search([])
        order._send_wishlist_update_email(
            self.wishlist,
            self.wishlist.line_ids,
            gift_message="Con mucho cariño para el bebé",
            gift_signature="Tío Juan",
        )
        mail = (self.env["mail.mail"].search([]) - before)
        self.assertTrue(mail, "Debe crearse el correo de actualización")
        body = mail[0].body_html
        self.assertIn("Con mucho cariño para el bebé", body)
        self.assertIn("Tío Juan", body)

    def test_email_without_gift_still_works(self):
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        before = self.env["mail.mail"].search([])
        order._send_wishlist_update_email(self.wishlist, self.wishlist.line_ids)
        mail = (self.env["mail.mail"].search([]) - before)
        self.assertTrue(mail)
