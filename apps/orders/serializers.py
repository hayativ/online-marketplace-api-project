# Django modules
from rest_framework.serializers import (
    ModelSerializer,
    StringRelatedField,
    SerializerMethodField,
    IntegerField,
)


# Project modules
from .models import (
    Order,
    OrderItem,
    CartItem,
    Review,
)
from apps.users.models import (
    CustomUser,
)


class ReviewSerializer(ModelSerializer):
    """Serializer for Review model."""

    user = StringRelatedField()

    class Meta:
        """Metadata."""

        model = Review
        fields = ["id", "user", "rate", "text"]
        read_only_fields = ["user"]


class CartItemBaseSerializer(ModelSerializer):
    """Serializer for CartItem model."""

    total_product_price = SerializerMethodField(
        method_name="get_total_product_price"
    )
    product = StringRelatedField()

    class Meta:
        """Metadata."""

        model = CartItem
        fields = (
            "id",
            "product",
            "quantity",
            "total_product_price",
        )

    def get_total_product_price(self, obj: CartItem) -> float:
        """Get total price for single position in a cart."""

        return round(obj.product.price * obj.quantity, 2)


class CartItemCreateSerializer(CartItemBaseSerializer):
    """Serializer for CartItem model. Handles the creation of new cart item."""

    user = StringRelatedField()

    class Meta:
        """Metadata."""
        model = CartItem
        fields = (
            "id",
            "user",
            "product",
            "quantity",
            "total_product_price",
        )
        read_only_fields = ["user", "id"]


class CartItemUpdateSerializer(CartItemBaseSerializer):
    """
    Serializer for CartItem model.
    Handles the partial update of a cart item.
    """
    user = StringRelatedField()

    class Meta:
        """Metadata."""
        model = CartItem
        fields = (
            "id",
            "user",
            "product",
            "quantity",
            "total_product_price",
        )
        read_only_fields = ["id", "user", "product"]


class CustomUserCartSerializer(ModelSerializer):
    cart_items = CartItemBaseSerializer(many=True)
    total_positions = IntegerField()

    class Meta:
        """Metadata."""
        model = CustomUser
        fields = (
            "id",
            "email",
            "total_positions",
            "cart_items",
        )


class OrderItemBaseSerializer(ModelSerializer):
    """Order Item Base Serializer."""

    total_product_price = SerializerMethodField(
        method_name="get_total_product_price"
    )

    class Meta:
        """Metadata."""

        model = OrderItem
        fields = (
            "id",
            "product",
            "name",
            "price",
            "quantity",
            "total_product_price",
        )

    def get_total_product_price(self, obj: OrderItem) -> float:
        """Get total price for single position in an order."""

        return round(obj.price * obj.quantity, 2)


class OrderListSerializer(ModelSerializer):
    """Serializer for list of orders."""

    user = StringRelatedField()
    order_items = OrderItemBaseSerializer(many=True)
    total_positions = IntegerField()

    class Meta:
        """Metadata."""
        model = Order
        fields = (
            "id",
            "user",
            "phone_number",
            "delivery_address",
            "status",
            "total_positions",
            "order_items",
        )
