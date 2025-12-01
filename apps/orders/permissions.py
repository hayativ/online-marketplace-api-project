# Django modules
from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.request import Request as DRFRequest
from rest_framework.views import APIView
from django.db.models import Model


class IsOwnerOrReadOnly(BasePermission):
    message = "Only owner can modify his content."

    def has_object_permission(
        self,
        request: DRFRequest,
        view: APIView,
        obj: Model,
    ):
        """Checks object permission."""

        if request.method in SAFE_METHODS:
            return True
        return request.user == obj.user
