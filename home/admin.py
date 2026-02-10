from django.contrib import admin

from .models import Booking, Favorite, Payment, Review, UserProfile, Vehicle, VehicleImage

admin.site.register(UserProfile)
admin.site.register(Vehicle)
admin.site.register(Booking)
admin.site.register(VehicleImage)
admin.site.register(Review)
admin.site.register(Favorite)
admin.site.register(Payment)

# Register your models here.
