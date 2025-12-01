# Python modules
from typing import Any

# Django modules
from rest_framework.viewsets import (
    ModelViewSet,
    ViewSet,
)
from rest_framework.views import APIView
from rest_framework.generics import (
    ListAPIView,
)
from django.shortcuts import get_object_or_404
from django.db.models import QuerySet, Count, Sum, F
from django.db import transaction
from rest_framework.permissions import (
    IsAuthenticatedOrReadOnly,
    IsAdminUser,
    IsAuthenticated,
)
from rest_framework.request import Request as DRFRequest
from rest_framework.response import Response as DRFResponse
from rest_framework.exceptions import PermissionDenied
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)
from rest_framework.pagination import PageNumberPagination
# Project modeules
from apps.products.models import Product
from .models import Review, Order, OrderItem, CartItem
from .serializers import (
    ReviewSerializer,
    CartItemBaseSerializer,
    CartItemCreateSerializer,
    CartItemUpdateSerializer,
    CustomUserCartSerializer,
    OrderListCreateSerializer,
)
from .permissions import IsOwnerOrReadOnly
from apps.users.models import CustomUser


class ReviewViewSet(ModelViewSet):
    """
    Handle all types of requests to reviews.
    """
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def get_product(self, product_id: int) -> Product:
        """Returns a product by id."""
        product = get_object_or_404(
            Product,
            id=product_id,
        )
        return product

    def get_queryset(self) -> QuerySet[Review]:
        """Get all reviews for the related product."""
        product = self.get_product(
            product_id=self.kwargs.get("product_id"),
        )

        return product.reviews.all()

    def perform_create(self, serializer):
        """Saves a new review with a current user as an author."""
        serializer.save(
            user=self.request.user,
            product=self.get_product(
                product_id=self.kwargs.get("product_id"),
            )
        )


class CartItemViewSet(ViewSet):
    """Viewset for handling CartItem related endpoints. """
    pagination_class = PageNumberPagination

    def get_permissions(self):
        """
        Instantiates and returns the
        list of permissions that this view requires.
        """
        if self.action == "list":
            permission_classes = [IsAdminUser]
        elif self.action in ["retrieve", "partial_update", "destroy"]:
            permission_classes = [IsOwnerOrReadOnly]
        elif self.action == "create":
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def list(
        self,
        request: DRFRequest,
        *args: tuple[Any, ...],
        **kwargs: dict[Any, Any],
    ) -> DRFResponse:
        """
        Handles GET requests to list of cart items.

        Parameters:
            request: DRFRequest
                The request object.
            *args: list
                Additional positional arguments.
            **kwargs: dict
                Additional keyword arguments.

        Returns:
            DRFResponse
                A response containing a list of all users cart items.
        """

        if not request.user.is_staff:
            raise PermissionDenied(
                "You can't access cart items of other users."
            )

        users: QuerySet[CustomUser] = CustomUser.objects.prefetch_related(
            "cart_items").annotate(
                total_positions=Count("cart_items__id")
        )

        paginator: PageNumberPagination = self.pagination_class()
        page = paginator.paginate_queryset(users, request=request)

        serializer: CustomUserCartSerializer = CustomUserCartSerializer(
            page,
            many=True,
        )

        return paginator.get_paginated_response(serializer.data)

    def retrieve(
        self,
        request: DRFRequest,
        pk: int,
        *args: tuple[Any, ...],
        **kwargs: dict[Any, Any],
    ) -> DRFResponse:
        """
        Handles GET requests to cart items of a single user.

        Parameters:
            request: DRFRequest
                The request object.
            pk: int
                User's id.
            *args: list
                Additional positional arguments.
            **kwargs: dict
                Additional keyword arguments.

        Returns:
            DRFResponse
                A response containing list of specified user's cart items.
        """

        user: CustomUser = get_object_or_404(CustomUser, pk=pk)

        # Check if the request was sent by staff or cart's owner:

        if request.user != user and not request.user.is_staff:
            raise PermissionDenied(
                "You can't access cart items of other users."
            )

        cart_items: QuerySet[CartItem] = CartItem.objects.filter(
            user=user,
        ).select_related("product")

        serializer: CartItemBaseSerializer = CartItemBaseSerializer(
            cart_items,
            many=True,
        )
        data: dict[str, dict[str, Any] | float | str] = {}
        data["user"] = user.email
        data["cart_items"] = serializer.data
        data["total"] = sum(
            (item["total_product_price"] for item in serializer.data)
        )
        return DRFResponse(data=data, status=HTTP_200_OK)

    def create(
        self,
        request: DRFRequest,
        *args: tuple[Any, ...],
        **kwargs: dict[Any, Any],
    ) -> DRFResponse:
        """
        Handles POST requests to add a new item to user's cart.

        Parameters:
            request: DRFRequest
                The request object.
            *args: list
                Additional positional arguments.
            **kwargs: dict
                Additional keyword arguments.

        Returns:
            DRFResponse
                A response containing information about added cart item.
        """

        request_data = request.data
        product: str = request_data.get("product")
        quantity: str | int = request_data.get("quantity") or 1

        if not product:
            return DRFResponse(
                data={
                    "product": ["Product can not be null."],
                },
                status=HTTP_400_BAD_REQUEST,
            )

        existing_cartitem: QuerySet[CartItem] = CartItem.objects.filter(
            user=request.user,
            product=product,
        ).first()

        if existing_cartitem:
            existing_cartitem.quantity += int(quantity)
            existing_cartitem.save()
            serializer: CartItemCreateSerializer = CartItemCreateSerializer(
                instance=existing_cartitem,
            )
        else:
            serializer: CartItemCreateSerializer = CartItemCreateSerializer(
                data=request_data,
            )
            if not serializer.is_valid():
                return DRFResponse(
                    data=serializer.errors,
                    status=HTTP_400_BAD_REQUEST,
                )
            serializer.save(
                user=request.user,
            )

        return DRFResponse(
            data=serializer.data,
            status=HTTP_201_CREATED,
        )

    def partial_update(
        self,
        request: DRFRequest,
        pk: int,
        *args: tuple[Any, ...],
        **kwargs: dict[Any, Any],
    ) -> DRFResponse:
        """
        Handles PATCH requests to partially update info
        about existing item in a cart.

        Parameters:
            request: DRFRequest
                The request object.
            pk: int
                Cart item id.
            *args: list
                Additional positional arguments.
            **kwargs: dict
                Additional keyword arguments.

        Returns:
            DRFResponse
                A response containing info about an updated item.
        """
        try:
            existing_cartitem: CartItem = CartItem.objects.get(pk=pk)
        except CartItem.DoesNotExist:
            return DRFResponse(
                data={
                    "pk": [f"CartItem with id={pk} does not exist."]
                },
                status=HTTP_404_NOT_FOUND,
            )

        self.check_object_permissions(request=request, obj=existing_cartitem)

        serializer: CartItemUpdateSerializer = CartItemUpdateSerializer(
            instance=existing_cartitem,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return DRFResponse(
            data=serializer.data,
            status=HTTP_200_OK,
        )

    def destroy(
        self,
        request: DRFRequest,
        pk: int,
        *args: tuple[Any, ...],
        **kwargs: dict[Any, Any],
    ) -> DRFResponse:
        """
        Handles DELETE requests to cart items.

        Parameters:
            request: DRFRequest
                The request object.
            pk: int
                Cart item id.
            *args: list
                Additional positional arguments.
            **kwargs: dict
                Additional keyword arguments.

        Returns:
            DRFResponse
                Status of the response.
        """
        try:
            existing_cartitem: CartItem = CartItem.objects.get(pk=pk)
        except CartItem.DoesNotExist:
            return DRFResponse(
                data={
                    "pk": [f"CartItem with id={pk} does not exist."]
                },
                status=HTTP_404_NOT_FOUND,
            )
        self.check_object_permissions(request=request, obj=existing_cartitem)
        existing_cartitem.delete()
        return DRFResponse(
            status=HTTP_204_NO_CONTENT,
        )


class OrderListView(ListAPIView):
    """
    Handles GET requests to Order model.
    """

    serializer_class = OrderListCreateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet[Order]:
        """Get a list of user's orders."""
        user = get_object_or_404(CustomUser, pk=self.kwargs.get("user_id"))

        user_orders = Order.objects.filter(user=user).prefetch_related(
            "order_items").annotate(
                total_positions=Count("order_items__id"),
                total_price=Sum(
                    F("order_items__price") * F("order_items__quantity")
                ),
        )

        return user_orders

    def get(
        self,
        request: DRFRequest,
        *args: tuple[Any, ...],
        **kwargs: dict[Any, Any],
    ) -> DRFResponse:
        """
        Handles GET requests to a list of specified user's orders.

        Parameters:
            request: DRFRequest
                The request object.
            *args: list
                Additional positional arguments.
            **kwargs: dict
                Additional keyword arguments.

        Returns:
            DRFResponse
                A response containing a list of user's orders.
        """

        if (
            request.user.id != self.kwargs.get("user_id") and
            not request.user.is_staff
        ):
            raise PermissionDenied("You can't access orders of other users.")

        return super().get(request, *args, **kwargs)


class OrderCreateView(APIView):
    """
    View to create a new order from existing cart items.
    """

    permission_classes = [IsAuthenticated]

    def post(
        self,
        request: DRFRequest,
        *args: tuple[Any, ...],
        **kwargs: dict[Any, Any],
    ) -> DRFResponse:
        """
        Handles POST requests to create a new order from exisiting items.
        Order is done by the user sending the request.

        Parameters:
            request: DRFRequest
                The request object.
            *args: list
                Additional positional arguments.
            **kwargs: dict
                Additional keyword arguments.

        Returns:
            DRFResponse
                A response containing info about a new order.
        """

        with transaction.atomic():
            user = request.user
            cart_items = CartItem.objects.filter(
                user=user).select_related("product")

            if not cart_items.exists():
                return DRFResponse(
                    data={
                        "cart_items": ["Your cart is empty."],
                    },
                    status=HTTP_400_BAD_REQUEST,
                )

            phone_number: str = request.data.get("phone_number")
            delivery_address: str = request.data.get("delivery_address")
            status: str = "P"

            if not phone_number or not delivery_address:
                return DRFResponse(
                    data={
                        "phone_number": ["Phone number can't be null."],
                        "delivery_address": ["Delivery address can't be null."]
                    },
                    status=HTTP_404_NOT_FOUND,
                )

            order: Order = Order.objects.create(
                user=request.user,
                phone_number=phone_number,
                delivery_address=delivery_address,
                status=status,
            )

            order_items: list[OrderItem] = []
            total_price: float = 0
            total_positions: int = 0

            for item in cart_items:
                product: Product = item.product
                name: str = item.product.name
                price: float = item.product.price
                quantity: int = item.quantity
                total_price += round(price * quantity, 2)
                total_positions += quantity

                order_items.append(
                    OrderItem(
                        order=order,
                        product=product,
                        name=name,
                        price=price,
                        quantity=quantity,
                    )
                )

            OrderItem.objects.bulk_create(order_items)
            cart_items.delete()

            serializer: OrderListCreateSerializer = OrderListCreateSerializer(
                instance=order,
                context={
                    "total_price": total_price,
                    "total_positions": total_positions,
                    },
            )

            return DRFResponse(
                data=serializer.data,
                status=HTTP_201_CREATED,
            )
