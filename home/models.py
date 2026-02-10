import random
import string
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    ROLE_CUSTOMER = "customer"
    ROLE_OWNER = "owner"
    ROLE_CHOICES = [
        (ROLE_CUSTOMER, "Customer"),
        (ROLE_OWNER, "Owner"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_CUSTOMER)
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self) -> str:
        return f"{self.user.username} ({self.role})"


class Vehicle(models.Model):
    TYPE_SEDAN = "sedan"
    TYPE_SUV = "suv"
    TYPE_HATCHBACK = "hatchback"
    TYPE_COUPE = "coupe"
    TYPE_CONVERTIBLE = "convertible"
    TYPE_PICKUP = "pickup"
    TYPE_VAN = "van"
    TYPE_CHOICES = [
        (TYPE_SEDAN, "Sedan"),
        (TYPE_SUV, "SUV"),
        (TYPE_HATCHBACK, "Hatchback"),
        (TYPE_COUPE, "Coupe"),
        (TYPE_CONVERTIBLE, "Convertible"),
        (TYPE_PICKUP, "Pickup"),
        (TYPE_VAN, "Van"),
    ]

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vehicles")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    city = models.CharField(max_length=200)
    location = models.CharField(max_length=200)
    pickup_location = models.CharField(max_length=200, blank=True)
    vehicle_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_SEDAN)
    make = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)
    seats = models.PositiveIntegerField(default=4)
    transmission = models.CharField(max_length=50, blank=True)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    daily_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    weekly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.title} - {self.location}"


class Booking(models.Model):
    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    UNIT_HOURLY = "hourly"
    UNIT_DAILY = "daily"
    UNIT_WEEKLY = "weekly"
    UNIT_CHOICES = [
        (UNIT_HOURLY, "Hourly"),
        (UNIT_DAILY, "Daily"),
        (UNIT_WEEKLY, "Weekly"),
    ]

    booking_id = models.CharField(max_length=40, unique=True, blank=True)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookings")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="bookings")
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    pickup_location = models.CharField(max_length=200, blank=True)
    dropoff_location = models.CharField(max_length=200, blank=True)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    pricing_unit = models.CharField(max_length=10, choices=UNIT_CHOICES)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self) -> None:
        if self.start_at >= self.end_at:
            raise ValidationError("Start time must be before end time.")

    def duration_hours(self) -> Decimal:
        delta = self.end_at - self.start_at
        return Decimal(delta.total_seconds()) / Decimal(3600)

    def calculate_total(self) -> Decimal:
        hours = self.duration_hours()
        if self.pricing_unit == self.UNIT_HOURLY:
            base = (hours * self.vehicle.hourly_rate).quantize(Decimal("0.01"))
            return (base + self.delivery_fee).quantize(Decimal("0.01"))
        if self.pricing_unit == self.UNIT_DAILY:
            days = (hours / Decimal(24)).quantize(Decimal("0.01"))
            base = (days * self.vehicle.daily_rate).quantize(Decimal("0.01"))
            return (base + self.delivery_fee).quantize(Decimal("0.01"))
        weeks = (hours / Decimal(24 * 7)).quantize(Decimal("0.01"))
        base = (weeks * self.vehicle.weekly_rate).quantize(Decimal("0.01"))
        return (base + self.delivery_fee).quantize(Decimal("0.01"))

    def save(self, *args, **kwargs) -> None:
        if timezone.is_naive(self.start_at) or timezone.is_naive(self.end_at):
            raise ValidationError("start_at and end_at must be timezone-aware.")
        if not self.booking_id:
            timestamp = timezone.now()
            date_part = timestamp.strftime("%Y%m%d%H%M%S")
            rand = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
            self.booking_id = f"BK{date_part}{rand}"
        self.full_clean()
        self.total_price = self.calculate_total()
        super().save(*args, **kwargs)


class VehicleImage(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="vehicle_images/")
    is_primary = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)


class Review(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="favorited_by")
    created_at = models.DateTimeField(auto_now_add=True)


class Payment(models.Model):
    STATUS_PENDING = "pending"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="payments")
    provider = models.CharField(max_length=50, default="cashfree")
    reference_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
