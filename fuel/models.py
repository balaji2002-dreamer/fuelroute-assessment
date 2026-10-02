from django.db import models


class FuelStop(models.Model):
    source_id = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=300, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2, db_index=True)
    price_per_gallon = models.DecimalField(max_digits=8, decimal_places=4)
    latitude = models.FloatField(null=True, blank=True, db_index=True)
    longitude = models.FloatField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["state", "price_per_gallon"])]

