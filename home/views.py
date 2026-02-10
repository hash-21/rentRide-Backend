from django.db import models
from django.db.models import Avg, Max, Min
from django.utils.dateparse import parse_datetime
from rest_framework import permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Booking, Favorite, Payment, Review, UserProfile, Vehicle, VehicleImage
from .permissions import IsCustomer, IsOwner, IsOwnerOrReadOnly
from .serializers import (
    BookingSerializer,
    LoginSerializer,
    FavoriteSerializer,
    PaymentSerializer,
    ReviewSerializer,
    RegisterSerializer,
    VehicleImageSerializer,
    VehicleSerializer,
)


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, token = serializer.save()
        return Response(
            {
                "token": token.key,
                "username": user.username,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "username": user.username})


class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.all().order_by("-created_at")
    serializer_class = VehicleSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset().filter(is_active=True)
        params = self.request.query_params
        location = params.get("location")
        seats_min = params.get("seats_min")
        seats_max = params.get("seats_max")
        seats = params.get("seats")
        transmission = params.get("transmission")
        vehicle_type = params.get("vehicle_type")
        pickup_location = params.get("pickup_location")
        price_min = params.get("price_min")
        price_max = params.get("price_max")
        search = params.get("search")
        sort = params.get("sort")
        start_at = params.get("start_at")
        end_at = params.get("end_at")
        available_only = params.get("available_only")

        if location:
            queryset = queryset.filter(location__icontains=location)
        if transmission:
            transmission_values = [value.strip() for value in transmission.split(",") if value.strip()]
            if transmission_values:
                queryset = queryset.filter(transmission__in=transmission_values)
        if vehicle_type:
            type_values = [value.strip() for value in vehicle_type.split(",") if value.strip()]
            if type_values:
                queryset = queryset.filter(vehicle_type__in=type_values)
        if pickup_location:
            queryset = queryset.filter(pickup_location__icontains=pickup_location)
        if seats:
            queryset = queryset.filter(seats=seats)
        if seats_min:
            queryset = queryset.filter(seats__gte=seats_min)
        if seats_max:
            queryset = queryset.filter(seats__lte=seats_max)
        if price_min:
            queryset = queryset.filter(hourly_rate__gte=price_min)
        if price_max:
            queryset = queryset.filter(hourly_rate__lte=price_max)
        if search:
            queryset = queryset.filter(
                models.Q(title__icontains=search)
                | models.Q(make__icontains=search)
                | models.Q(model__icontains=search)
            )

        if start_at and end_at and available_only in {"1", "true", "yes"}:
            parsed_start = parse_datetime(start_at)
            parsed_end = parse_datetime(end_at)
            if parsed_start and parsed_end:
                conflict_ids = Booking.objects.filter(
                    start_at__lt=parsed_end,
                    end_at__gt=parsed_start,
                    status__in=[Booking.STATUS_PENDING, Booking.STATUS_CONFIRMED],
                ).values_list("vehicle_id", flat=True)
                queryset = queryset.exclude(id__in=conflict_ids)

        if sort == "price":
            queryset = queryset.order_by("hourly_rate")
        elif sort == "-price":
            queryset = queryset.order_by("-hourly_rate")
        elif sort == "newest":
            queryset = queryset.order_by("-created_at")
        elif sort == "rating":
            queryset = queryset.annotate(avg_rating=Avg("reviews__rating")).order_by("-avg_rating")

        return queryset

    def perform_create(self, serializer):
        if not IsOwner().has_permission(self.request, self):
            raise PermissionDenied("Only owners can add vehicles.")
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["get"])
    def quote(self, request, pk=None):
        vehicle = self.get_object()
        start_at = request.query_params.get("start_at")
        end_at = request.query_params.get("end_at")
        pricing_unit = request.query_params.get("pricing_unit")
        if not (start_at and end_at and pricing_unit):
            return Response(
                {"detail": "start_at, end_at, and pricing_unit are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        parsed_start = parse_datetime(start_at)
        parsed_end = parse_datetime(end_at)
        if not (parsed_start and parsed_end):
            return Response({"detail": "Invalid datetime format."}, status=status.HTTP_400_BAD_REQUEST)
        booking = Booking(
            vehicle=vehicle,
            start_at=parsed_start,
            end_at=parsed_end,
            pricing_unit=pricing_unit,
        )
        try:
            total = booking.calculate_total()
        except Exception:
            return Response({"detail": "Unable to calculate total."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"vehicle_id": vehicle.id, "total_price": str(total)})

    @action(detail=True, methods=["get"])
    def availability(self, request, pk=None):
        vehicle = self.get_object()
        start_at = request.query_params.get("start_at")
        end_at = request.query_params.get("end_at")
        if not (start_at and end_at):
            return Response(
                {"detail": "start_at and end_at are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        parsed_start = parse_datetime(start_at)
        parsed_end = parse_datetime(end_at)
        if not (parsed_start and parsed_end):
            return Response({"detail": "Invalid datetime format."}, status=status.HTTP_400_BAD_REQUEST)
        bookings = vehicle.bookings.filter(
            start_at__lt=parsed_end,
            end_at__gt=parsed_start,
            status__in=[Booking.STATUS_PENDING, Booking.STATUS_CONFIRMED],
        ).order_by("start_at")
        data = [
            {"start_at": b.start_at, "end_at": b.end_at, "status": b.status}
            for b in bookings
        ]
        return Response({"vehicle_id": vehicle.id, "booked_slots": data})


class VehicleImageViewSet(viewsets.ModelViewSet):
    serializer_class = VehicleImageSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return VehicleImage.objects.filter(vehicle__owner=self.request.user)

    def perform_create(self, serializer):
        vehicle = serializer.validated_data["vehicle"]
        if vehicle.owner != self.request.user:
            raise PermissionDenied("You can only upload images for your vehicles.")
        serializer.save()


class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        vehicle_id = self.request.query_params.get("vehicle")
        queryset = Review.objects.all().order_by("-created_at")
        if vehicle_id:
            queryset = queryset.filter(vehicle_id=vehicle_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save(reviewer=self.request.user)


class FavoriteViewSet(viewsets.ModelViewSet):
    serializer_class = FavoriteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Favorite.objects.filter(user=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class BookingViewSet(viewsets.ModelViewSet):
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated, IsCustomer]

    def get_queryset(self):
        return Booking.objects.filter(customer=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        vehicle = serializer.validated_data["vehicle"]
        start_at = serializer.validated_data["start_at"]
        end_at = serializer.validated_data["end_at"]
        pickup_location = serializer.validated_data.get("pickup_location") or vehicle.pickup_location
        delivery_fee = serializer.validated_data.get("delivery_fee")
        if delivery_fee is None:
            delivery_fee = vehicle.delivery_fee
        overlap = Booking.objects.filter(
            vehicle=vehicle,
            start_at__lt=end_at,
            end_at__gt=start_at,
            status__in=[Booking.STATUS_PENDING, Booking.STATUS_CONFIRMED],
        ).exists()
        if overlap:
            raise PermissionDenied("Vehicle is not available in the selected time window.")
        serializer.save(
            customer=self.request.user,
            pickup_location=pickup_location,
            delivery_fee=delivery_fee,
        )

    @action(detail=True, methods=["post"])
    def checkout(self, request, pk=None):
        booking = self.get_object()
        if booking.status != Booking.STATUS_PENDING:
            return Response({"detail": "Booking is not pending."}, status=status.HTTP_400_BAD_REQUEST)
        payment = Payment.objects.create(
            booking=booking,
            amount=booking.total_price,
            status=Payment.STATUS_PENDING,
        )
        payment.reference_id = str(payment.id)
        payment.save()
        data = PaymentSerializer(payment).data
        data["message"] = "Integrate Cashfree payment here."
        return Response(data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        if booking.status == Booking.STATUS_CANCELLED:
            return Response({"detail": "Booking already cancelled."}, status=status.HTTP_400_BAD_REQUEST)
        booking.status = Booking.STATUS_CANCELLED
        booking.save()
        return Response({"detail": "Booking cancelled."})

    @action(detail=False, methods=["get"])
    def previous(self, request):
        queryset = Booking.objects.filter(
            customer=request.user,
            status__in=[Booking.STATUS_CONFIRMED, Booking.STATUS_CANCELLED],
        ).order_by("-created_at")
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class OwnerBookingViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return Booking.objects.filter(vehicle__owner=self.request.user).order_by("-created_at")

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        booking = self.get_object()
        booking.status = Booking.STATUS_CONFIRMED
        booking.save()
        return Response({"detail": "Booking confirmed."})

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        booking = self.get_object()
        booking.status = Booking.STATUS_CANCELLED
        booking.save()
        return Response({"detail": "Booking rejected."})


class FilterOptionsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        price_stats = Vehicle.objects.aggregate(min_price=Min("hourly_rate"), max_price=Max("hourly_rate"))
        seats_stats = Vehicle.objects.aggregate(min_seats=Min("seats"), max_seats=Max("seats"))
        return Response(
            {
                "vehicle_types": [choice[0] for choice in Vehicle.TYPE_CHOICES],
                "transmissions": list(
                    Vehicle.objects.exclude(transmission="").values_list("transmission", flat=True).distinct()
                ),
                "min_hourly_rate": price_stats.get("min_price"),
                "max_hourly_rate": price_stats.get("max_price"),
                "min_seats": seats_stats.get("min_seats"),
                "max_seats": seats_stats.get("max_seats"),
            }
        )


class PaymentWebhookView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        reference_id = request.data.get("reference_id")
        status_value = request.data.get("status")
        payment = None
        if reference_id:
            try:
                payment = Payment.objects.get(reference_id=reference_id)
            except Payment.DoesNotExist:
                payment = None
        if not payment:
            booking_id = request.data.get("booking_id")
            if not booking_id:
                return Response({"detail": "reference_id or booking_id required."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                booking = Booking.objects.get(id=booking_id)
            except Booking.DoesNotExist:
                return Response({"detail": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)
            payment = Payment.objects.create(
                booking=booking,
                amount=booking.total_price,
                reference_id=reference_id or "",
            )
        payment.status = status_value or payment.status
        payment.payload = request.data
        payment.save()
        if payment.status == Payment.STATUS_SUCCESS:
            payment.booking.status = Booking.STATUS_CONFIRMED
            payment.booking.save()
        return Response({"detail": "Webhook processed."})


class UserProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            profile = user.userprofile
            role = 'admin' if user.is_staff else profile.role
            phone = profile.phone
        except UserProfile.DoesNotExist:
            role = 'admin' if user.is_staff else 'customer'
            phone = ''
        
        return Response({
            'username': user.username,
            'email': user.email,
            'role': role,
            'is_staff': user.is_staff,
            'phone': phone
        })
    
    def patch(self, request):
        user = request.user
        data = request.data
        
        # Update User model fields
        if 'email' in data:
            user.email = data['email']
            user.save()
        
        # Update or create UserProfile
        try:
            profile = user.userprofile
        except UserProfile.DoesNotExist:
            profile = UserProfile.objects.create(user=user)
        
        if 'phone' in data:
            profile.phone = data['phone']
            profile.save()
        
        return Response({
            'username': user.username,
            'email': user.email,
            'role': 'admin' if user.is_staff else profile.role,
            'is_staff': user.is_staff,
            'phone': profile.phone
        })


class AdminStatsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        return Response(
            {
                "vehicles": Vehicle.objects.count(),
                "bookings": Booking.objects.count(),
                "active_owners": UserProfile.objects.filter(role=UserProfile.ROLE_OWNER).count(),
                "active_customers": UserProfile.objects.filter(role=UserProfile.ROLE_CUSTOMER).count(),
            }
        )
