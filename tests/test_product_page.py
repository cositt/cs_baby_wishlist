from lxml import html

from odoo.tests import HttpCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestProductPageWishlistModal(HttpCase):
    """«+ lista deseo» en la ficha de producto: el formulario del modal no puede
    quedar anidado dentro del formulario de añadir al carrito (el navegador
    descarta el <form> interior y «Añadir» deja de funcionar)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(
            cls.env, login="wl_parent", password="wl_parent_pwd", groups="base.group_portal"
        )
        cls.product = cls.env["product.template"].create(
            {"name": "Cuna de prueba", "list_price": 100.0, "sale_ok": True, "is_published": True}
        )
        cls.wishlist = cls.env["wishlist.list"].create(
            {"name": "Lista de prueba", "customer_id": cls.user.partner_id.id, "state": "active"}
        )

    def _product_page(self):
        self.authenticate("wl_parent", "wl_parent_pwd")
        response = self.url_open(self.product.website_url)
        self.assertEqual(response.status_code, 200)
        return response.text

    def test_modal_form_not_nested_in_cart_form(self):
        page = self._product_page()
        # Everything before the modal's own <form> tag must have every <form> closed.
        start = page.rindex("<form", 0, page.index('action="/wishlist/catalog/add"'))
        before = page[:start]
        self.assertEqual(
            before.count("<form"),
            before.count("</form>"),
            "El formulario del modal está anidado dentro de otro formulario",
        )

    def test_modal_form_posts_product_and_wishlist(self):
        tree = html.fromstring(self._product_page())
        forms = tree.xpath("//form[@action='/wishlist/catalog/add']")
        self.assertEqual(len(forms), 1)
        form = forms[0]
        self.assertTrue(form.xpath(".//input[@name='product_id' and @value]"))
        self.assertTrue(form.xpath(".//select[@name='wishlist_id']/option[@value='%d']" % self.wishlist.id))
        self.assertTrue(form.xpath(".//input[@name='csrf_token']"))
        self.assertTrue(tree.xpath("//button[@data-bs-target='#wishlistModalDetail']"))
