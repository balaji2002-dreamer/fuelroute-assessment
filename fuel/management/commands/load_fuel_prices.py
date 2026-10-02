import csv
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from geonamescache import GeonamesCache

from fuel.models import FuelStop


class Command(BaseCommand):
    help = "Import fuel prices and attach offline city-centroid coordinates."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", help="Path to fuel-prices-for-be-assessment.csv")

    def handle(self, *args, **options):
        path = options["csv_path"]
        try:
            with open(path, newline="", encoding="utf-8-sig") as source:
                rows = list(csv.DictReader(source))
        except OSError as exc:
            raise CommandError(str(exc)) from exc
        required = {"OPIS Truckstop ID", "Truckstop Name", "Address", "City", "State", "Retail Price"}
        if not rows or not required.issubset(rows[0]):
            raise CommandError("CSV is empty or missing expected fuel price columns.")
        def normalize(value):
            return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))

        # The source has no coordinates. Match its city/state to GeoNames' offline
        # US gazetteer, which gives a consistent locality-centroid approximation.
        gazetteer = GeonamesCache(min_city_population=500).get_cities().values()
        places = {}
        for place in gazetteer:
            if place["countrycode"] != "US":
                continue
            point = (float(place["latitude"]), float(place["longitude"]))
            for name in [place["name"], *place.get("alternatenames", [])]:
                places.setdefault((normalize(name), place["admin1code"].upper()), point)
        fuel_stops = []
        unmatched = set()
        for row_number, row in enumerate(rows, start=1):
            locality = (row["City"].strip(), row["State"].strip())
            point = places.get((normalize(locality[0]), locality[1].upper()))
            if point is None:
                unmatched.add(locality)
                continue
            # Include the CSV line number: OPIS IDs can repeat for different records.
            fuel_stops.append(FuelStop(source_id=f"{row['OPIS Truckstop ID'].strip()}:{row_number}", name=row["Truckstop Name"].strip(), address=row["Address"].strip(), city=locality[0], state=locality[1].upper(), price_per_gallon=row["Retail Price"], latitude=point[0], longitude=point[1]))
        with transaction.atomic():
            FuelStop.objects.all().delete()
            FuelStop.objects.bulk_create(fuel_stops, batch_size=1000)
        imported = len(fuel_stops)
        self.stdout.write(self.style.SUCCESS(f"Imported {imported} fuel records using offline city-centroid coordinates."))
        if unmatched:
            self.stdout.write(self.style.WARNING(f"Skipped {len(unmatched)} unmatched city/state pairs."))

