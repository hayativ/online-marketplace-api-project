# Django modules
from django.urls import include, path
from rest_framework.routers import DefaultRouter

# Project modules
from .views import (
    ReviewViewSet,
    CartItemViewSet,
    OrderListView,
    OrderCreateView
)

v1_router = DefaultRouter()
v1_router.register(
    r"products/(?P<product_id>\d+)/reviews",
    ReviewViewSet,
    basename="reviews",
)

carts_list = CartItemViewSet.as_view({"get": "list", "post": "create"})
users_cart = CartItemViewSet.as_view({"get": "retrieve"})
cart_item_update = CartItemViewSet.as_view(
    {"patch": "partial_update", "delete": "destroy"}
)

urlpatterns = [
    path("", include(v1_router.urls)),
    path("users/carts/", carts_list, name="users-carts"),
    path("users/<int:user_id>/carts/", users_cart, name="user-cart"),
    path("users/carts/<int:pk>/",
         cart_item_update, name="user-cart-update-destroy"),
    path("users/<int:user_id>/orders/",
         OrderListView.as_view(), name="user-orders"),
    path("users/orders/",
         OrderCreateView.as_view(), name="order-create"),
]
