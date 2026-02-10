import os
import mimetypes
from decimal import Decimal
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from home.models import UserProfile, Vehicle, VehicleImage


IMAGE_URLS = [
    "https://imgd.aeplcdn.com/370x208/cw/ec/38219/Mahindra-XUV300-Exterior-147500.jpg?wm=0&q=80",
    "https://spn-sta.spinny.com/blog/20220228135118/2021-Jeep-Compass-Header-2.jpg",
    "https://spn-sta.spinny.com/blog/20221212163811/Best-premium-hatchback-cars-in-india-jpg.webp",
    "https://www.autobest.co.in/uploads/blog/407601293444.jpeg",
    "https://flywheelcars.com/wp-content/uploads/2023/10/376402746_730795669059848_8081543603182068029_n-1024x768.jpg"
]


DELHI_LOCATIONS = [
    {"location": "Connaught Place, New Delhi", "pickup_location": "Rajiv Chowk Metro Station, New Delhi"},
    {"location": "Saket, New Delhi", "pickup_location": "Saket Metro Station, New Delhi"},
    {"location": "Karol Bagh, New Delhi", "pickup_location": "Karol Bagh Metro Station, New Delhi"},
    {"location": "Dwarka Sector 21, New Delhi", "pickup_location": "Dwarka Sector 21 Metro Station, New Delhi"},
    {"location": "Vasant Kunj, New Delhi", "pickup_location": "Vasant Vihar Metro Station, New Delhi"},
    {"location": "Rohini Sector 18, New Delhi", "pickup_location": "Rohini West Metro Station, New Delhi"},
]


def _safe_filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    name = os.path.basename(parsed.path) or "image"
    return name.split("?")[0].strip() or "image"


def _download_bytes(url: str, timeout: int = 25) -> tuple[bytes, str]:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=timeout) as resp:
        content = resp.read()
        content_type = resp.headers.get("Content-Type", "").split(";")[0].strip()
        return content, content_type


def _ext_from_content_type(content_type: str) -> str:
    if not content_type:
        return ""
    ext = mimetypes.guess_extension(content_type)
    return ext or ""


class Command(BaseCommand):
    help = "Seeds demo data: owners, vehicles, and vehicle images (Delhi-only addresses)."

    @transaction.atomic
    def handle(self, *args, **options):
        if not getattr(settings, "MEDIA_ROOT", None):
            raise CommandError("MEDIA_ROOT is not set. Configure MEDIA_ROOT before running this command.")

        User = get_user_model()

        owners_data = [
            {"username": "Abhijeet Gupta", "email": "abhijeet@gmail.com", "phone": "9000000001"},
            {"username": "Nitesh Upadhyay", "email": "nitesh@gmail.com", "phone": "9000000002"},
        ]

        owners = []
        for od in owners_data:
            user, created = User.objects.get_or_create(
                username=od["username"],
                defaults={"email": od["email"]},
            )
            if created:
                user.set_password("Demo@12345")
                user.save(update_fields=["password"])
            UserProfile.objects.get_or_create(
                user=user,
                defaults={"role": UserProfile.ROLE_OWNER, "phone": od["phone"]},
            )
            owners.append(user)

        vehicles_seed = [
            {
                "owner": owners[0],
                "title": "Mahindra XUV300 ",
                "description": "Delhi demo listing for UI showcase.",
                "vehicle_type": Vehicle.TYPE_SUV,
                "make": "Mahindra",
                "model": "XUV300",
                "year": 2022,
                "seats": 5,
                "transmission": "Manual",
                "hourly_rate": Decimal("299.00"),
                "daily_rate": Decimal("1999.00"),
                "weekly_rate": Decimal("11999.00"),
                "delivery_fee": Decimal("149.00"),
                "is_active": True,
            },
            {
                "owner": owners[0],
                "title": "Jeep Compass ",
                "description": "Premium SUV demo listing (Delhi).",
                "vehicle_type": Vehicle.TYPE_SUV,
                "make": "Jeep",
                "model": "Compass",
                "year": 2021,
                "seats": 5,
                "transmission": "Automatic",
                "hourly_rate": Decimal("399.00"),
                "daily_rate": Decimal("2499.00"),
                "weekly_rate": Decimal("14999.00"),
                "delivery_fee": Decimal("199.00"),
                "is_active": True,
            },
            {
                "owner": owners[1],
                "title": "Premium Hatchback ",
                "description": "Hatchback demo listing for Delhi users.",
                "vehicle_type": Vehicle.TYPE_HATCHBACK,
                "make": "Hyundai",
                "model": "i20",
                "year": 2023,
                "seats": 5,
                "transmission": "Manual",
                "hourly_rate": Decimal("249.00"),
                "daily_rate": Decimal("1599.00"),
                "weekly_rate": Decimal("9999.00"),
                "delivery_fee": Decimal("99.00"),
                "is_active": True,
            },
            {
                "owner": owners[1],
                "title": "Honda City ",
                "description": "Sedan demo listing for Delhi.",
                "vehicle_type": Vehicle.TYPE_SEDAN,
                "make": "Honda",
                "model": "City",
                "year": 2020,
                "seats": 5,
                "transmission": "Automatic",
                "hourly_rate": Decimal("279.00"),
                "daily_rate": Decimal("1799.00"),
                "weekly_rate": Decimal("10999.00"),
                "delivery_fee": Decimal("129.00"),
                "is_active": True,
            },
        ]

        # Download images once
        downloaded = []
        for url in IMAGE_URLS:
            content, content_type = _download_bytes(url)
            base = _safe_filename_from_url(url)
            ext = os.path.splitext(base)[1]
            if not ext:
                ext = _ext_from_content_type(content_type)
            if not ext:
                ext = ".jpg"
            final_name = f"{os.path.splitext(base)[0]}{ext}"
            downloaded.append((final_name, content))

        created_vehicles = []
        for idx, vd in enumerate(vehicles_seed):
            loc = DELHI_LOCATIONS[idx % len(DELHI_LOCATIONS)]

            defaults = {
                **vd,
                "city": "Delhi",
                "location": loc["location"],
                "pickup_location": loc["pickup_location"],
            }

            vehicle, _ = Vehicle.objects.update_or_create(
                owner=vd["owner"],
                title=vd["title"],
                defaults=defaults,
            )
            created_vehicles.append(vehicle)

        total_images = 0
        for vehicle in created_vehicles:
            VehicleImage.objects.filter(vehicle=vehicle).delete()

            for img_idx, (fname, content) in enumerate(downloaded):
                vi = VehicleImage(vehicle=vehicle, is_primary=(img_idx == 0))
                vi.image.save(fname, ContentFile(content), save=True)
                total_images += 1

        self.stdout.write(self.style.SUCCESS("✅ Demo seed complete"))
        self.stdout.write(self.style.SUCCESS(f"Owners: {len(owners)}"))
        self.stdout.write(self.style.SUCCESS(f"Vehicles: {len(created_vehicles)}"))
        self.stdout.write(self.style.SUCCESS(f"VehicleImages: {total_images}"))
        self.stdout.write(self.style.WARNING("Login creds: demo_owner_1 / Demo@12345 and demo_owner_2 / Demo@12345"))
