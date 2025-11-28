# Python modules
from typing import Any

# Django modules
from rest_framework.viewsets import (
    ModelViewSet,
    ViewSet,
)
from rest_framework.mixins import (
    ListModelMixin,
)
from rest_framework.generics import (
    GenericAPIView,
    ListAPIView,
)
from django.shortcuts import get_object_or_404
from django.db.models import QuerySet, Count
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
    OrderListSerializer,
)
from .permissions import IsOwnerOrReadOnly
from apps.users.models import CustomUser


class ReviewViewSet(ModelViewSet):
    """ViewSet for Review model."""
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
        elif self.action == "retrieve":
            permission_classes = [IsAdminUser, IsOwnerOrReadOnly]
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
        Returns carts of all users.
        """

        # if not request.user.is_staff:
        #     raise PermissionDenied(
        #         "You can't access cart items of other users."
        #     )

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

        return DRFResponse(data=serializer.data, status=HTTP_200_OK)

    def retrieve(
        self,
        request: DRFRequest,
        pk: int,
        *args: tuple[Any, ...],
        **kwargs: dict[Any, Any],
    ) -> DRFResponse:
        """
        Handles GET requests to list of cart items.
        Returns a list of cart items of a user by specified id.
        """
        user: CustomUser = get_object_or_404(CustomUser, pk=pk)

        # Check if the request was sent by staff or cart's owner:

        # if request.user != user and not request.user.is_staff:
        #     raise PermissionDenied(
        #         "You can't access cart items of other users."
        #     )

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
        Handles PATCH requests to update an existing CartItem instance.
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
        Handles DELETE requests to destroy an existing CartItem instance.
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
        existing_cartitem.delete()
        return DRFResponse(
            status=HTTP_204_NO_CONTENT,
        )


class OrderViewSet(ListAPIView):
    """
    Handles GET requests to Order model.
    """

    serializer_class = OrderListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet[Order]:
        """Get a list of user's orders."""
        user = get_object_or_404(CustomUser, pk=self.kwargs.get("user_id"))

        user_orders = Order.objects.filter(user=user).prefetch_related(
            "order_items").annotate(
                total_positions=Count("order_items__id")
            )

        return user_orders

    def get(
        self,
        request: DRFRequest,
        *args: tuple[Any, ...],
        **kwargs: dict[Any, Any],
    ) -> DRFResponse:
        """Handles GET requests to a list of specified user's orders."""

        if request.user.id != self.kwargs.get("user_id") and not request.user.is_staff:
            raise PermissionDenied("You can't access orders of other users.")

        return super().get(request, *args, **kwargs)
