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
