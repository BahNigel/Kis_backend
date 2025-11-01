from rest_framework import serializers
from .models import (Shop, ShopVerificationRequest, Product, ProductAuthenticityCheck, Order, OrderItem,
                     Payment, Promotion, Subscription, LoyaltyPoint, ShopFollow, ProductShare, AIRecommendation,
                     AuditLog, FraudSignal)


class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = '__all__'
        read_only_fields = ('owner', 'is_verified', 'verification_status', 'trust_badges')


class ShopVerificationRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopVerificationRequest
        fields = '__all__'
        read_only_fields = ('status', 'risk_score', 'processed_at')


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'
        read_only_fields = ('ai_score', 'authenticity_status', 'authenticity_proof')


class ProductAuthenticityCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductAuthenticityCheck
        fields = '__all__'
        read_only_fields = ('status', 'result', 'confidence', 'checked_at')


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = '__all__'


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = '__all__'
        read_only_fields = ('status','subtotal','total')

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        order = Order.objects.create(**validated_data)
        subtotal = 0
        for item in items_data:
            OrderItem.objects.create(order=order, **item)
            subtotal += float(item['unit_price']) * int(item.get('quantity',1))
        order.subtotal = subtotal
        order.total = subtotal + float(order.tax) + float(order.shipping) - float(order.discount_amount)
        order.save()
        return order


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'


class PromotionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Promotion
        fields = '__all__'


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = '__all__'


class LoyaltyPointSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoyaltyPoint
        fields = '__all__'


class ShopFollowSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopFollow
        fields = '__all__'
        read_only_fields = ('followed_at',)


class ProductShareSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductShare
        fields = '__all__'


class AIRecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIRecommendation
        fields = '__all__'


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = '__all__'


class FraudSignalSerializer(serializers.ModelSerializer):
    class Meta:
        model = FraudSignal
        fields = '__all__'
