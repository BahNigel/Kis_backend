
from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Shop, Product


class CommerceSmokeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='seller', password='pass')
        self.shop = Shop.objects.create(owner=self.user, name='My Shop', slug='my-shop')

    def test_create_product(self):
        p = Product.objects.create(shop=self.shop, sku='TEST-001', name='Test Product', price=1000)
        self.assertEqual(p.shop, self.shop)