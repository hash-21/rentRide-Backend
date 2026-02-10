from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AdminStatsView,
    BookingViewSet,
    FavoriteViewSet,
    FilterOptionsView,
    LoginView,
    OwnerBookingViewSet,
    PaymentWebhookView,
    RegisterView,
    ReviewViewSet,
    UserProfileView,
    VehicleImageViewSet,
    VehicleViewSet,
)

router = DefaultRouter()
router.register("vehicles", VehicleViewSet, basename="vehicle")
router.register("vehicle-images", VehicleImageViewSet, basename="vehicle-image")
router.register("reviews", ReviewViewSet, basename="review")
router.register("favorites", FavoriteViewSet, basename="favorite")
router.register("bookings", BookingViewSet, basename="booking")
router.register("owner-bookings", OwnerBookingViewSet, basename="owner-booking")

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("user/profile/", UserProfileView.as_view(), name="user-profile"),
    path("filters/", FilterOptionsView.as_view(), name="filters"),
    path("payments/webhook/", PaymentWebhookView.as_view(), name="payment-webhook"),
    path("admin/stats/", AdminStatsView.as_view(), name="admin-stats"),
    path("", include(router.urls)),
]
