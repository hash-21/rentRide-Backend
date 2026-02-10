from rest_framework import permissions

from .models import UserProfile


def _has_role(user, role: str) -> bool:
    if not user or not user.is_authenticated:
        return False
    try:
        return user.userprofile.role == role
    except UserProfile.DoesNotExist:
        return False


class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.owner == request.user


class IsOwner(permissions.BasePermission):
    def has_permission(self, request, view):
        return _has_role(request.user, UserProfile.ROLE_OWNER)


class IsCustomer(permissions.BasePermission):
    def has_permission(self, request, view):
        return _has_role(request.user, UserProfile.ROLE_CUSTOMER)
