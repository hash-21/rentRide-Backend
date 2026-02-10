from django.contrib.auth import authenticate, get_user_model
from django.utils.dateparse import parse_datetime
from rest_framework import serializers
from rest_framework.authtoken.models import Token

from .models import Booking, Favorite, Payment, Review, UserProfile, Vehicle, VehicleImage

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(choices=UserProfile.ROLE_CHOICES, default=UserProfile.ROLE_CUSTOMER)
    phone = serializers.CharField(required=False, allow_blank=True)

    def create(self, validated_data):
        role = validated_data.pop("role")
        phone = validated_data.pop("phone", "")
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        UserProfile.objects.create(user=user, role=role, phone=phone)
        token, _ = Token.objects.get_or_create(user=user)
        return user, token


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(username=attrs["username"], password=attrs["password"])
        if not user:
            raise serializers.ValidationError("Invalid credentials.")
        attrs["user"] = user
        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["role", "phone"]


class VehicleSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source="owner.username")
    avg_rating = serializers.SerializerMethodField()
    is_booked = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()

    class Meta:
        model = Vehicle
        fields = [
            "id",
            "owner",
            "title",
            "description",
            "location",
            "pickup_location",
            "vehicle_type",
            "make",
            "model",
            "year",
            "seats",
            "transmission",
            "hourly_rate",
            "daily_rate",
            "weekly_rate",
            "delivery_fee",
            "is_active",
            "avg_rating",
            "is_booked",
            "images",
            "created_at",
        ]

    def get_avg_rating(self, obj):
        reviews = obj.reviews.all()
        if not reviews:
            return None
        total = sum(review.rating for review in reviews)
        return round(total / reviews.count(), 2)

    def get_is_booked(self, obj):
        request = self.context.get("request")
        if not request:
            return False
        start_at = request.query_params.get("start_at")
        end_at = request.query_params.get("end_at")
        if not (start_at and end_at):
            return False
        parsed_start = parse_datetime(start_at)
        parsed_end = parse_datetime(end_at)
        if not (parsed_start and parsed_end):
            return False
        return obj.bookings.filter(
            start_at__lt=parsed_end,
            end_at__gt=parsed_start,
            status__in=[Booking.STATUS_PENDING, Booking.STATUS_CONFIRMED],
        ).exists()

    def get_images(self, obj):
        return [f"http://127.0.0.1:8000{image.image.url}" for image in obj.images.all()]


class VehicleImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleImage
        fields = ["id", "vehicle", "image", "is_primary", "uploaded_at"]


class ReviewSerializer(serializers.ModelSerializer):
    reviewer = serializers.ReadOnlyField(source="reviewer.username")

    class Meta:
        model = Review
        fields = ["id", "vehicle", "reviewer", "rating", "comment", "created_at"]

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value


class FavoriteSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source="user.username")

    class Meta:
        model = Favorite
        fields = ["id", "user", "vehicle", "created_at"]


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "booking", "provider", "reference_id", "status", "amount", "created_at"]


class BookingSerializer(serializers.ModelSerializer):
    customer = serializers.ReadOnlyField(source="customer.username")
    vehicle_title = serializers.ReadOnlyField(source="vehicle.title")

    class Meta:
        model = Booking
        fields = [
            "id",
            "booking_id",
            "customer",
            "vehicle",
            "vehicle_title",
            "start_at",
            "end_at",
            "pickup_location",
            "dropoff_location",
            "delivery_fee",
            "pricing_unit",
            "total_price",
            "status",
            "created_at",
        ]
        read_only_fields = ["total_price", "status", "created_at"]
