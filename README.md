# FuelRoute

Django API that returns a US driving route, nearby low-price fuel stops, an interactive MapLibre route map, and an estimated trip fuel cost.

## Stack and provider calls

- Django 6.1.1 (current stable release at the time this assignment was prepared), SQLite, and a MapLibre GL JS browser map.
- One route request to the public OSRM routing service per itinerary.
- Two sequential Nominatim geocoding requests when both endpoints are uncached. The process cache reuses prior endpoint lookups, and cold requests are paced to Nominatim's public limit. Each itinerary makes at most three provider calls. Configure an identifying `GEOCODER_USER_AGENT` with contact details, and use a hosted/self-managed provider for production or sustained traffic.
- Fuel prices are stored locally. The CSV has no coordinates, so the import command matches city/state pairs against the offline GeoNames city gazetteer. Fuel-stop map points are city-centroid estimates and can be up to 25 miles from the route; the source does not provide exact station coordinates.
- The map uses the free OpenFreeMap vector basemap with OpenStreetMap/OpenFreeMap attribution; routing is attributed to OSRM.

## Setup

Requires Python 3.12+ and a network connection for initial data import and route lookups.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate --run-syncdb
python manage.py load_fuel_prices .\data\fuel-prices-for-be-assessment.csv
python manage.py runserver
```

Then open http://127.0.0.1:8000. Add your own contact email to the default `GEOCODER_USER_AGENT` in `config/settings.py` before running the public geocoder.

## API

`GET /api/route/?start=Boston%2C%20MA&finish=New%20York%2C%20NY`

Returns endpoint resolution, distance and duration, 10 MPG and 500 mile range assumptions, estimated fuel cost, an array of fuel stops (with route mileage, price, gallons and cost), and route geometry as GeoJSON `LineString` for mapping. Both location strings must include a US state abbreviation. Missing or invalid inputs return a 400 response; unroutable locations return a 422; provider failures return 502/504.

The fuel planner greedily chooses the lowest-priced mapped stop within the next 500 route miles and within 25 miles of the route. Because the CSV has no precise station coordinates and no starting tank level is specified, stop positions and fuel cost are estimates. Each traveled leg's gallons are priced at the selected stop for that leg (including the first leg). Actual tank fullness, detour mileage, station availability, and price changes are not modeled. GeoNames city data is distributed under CC BY 4.0; see [GeoNames](https://www.geonames.org/) for attribution and licensing.

## Postman demo

1. Run the setup commands above and confirm the web page displays the form.
2. In Postman, send `GET http://127.0.0.1:8000/api/route/?start=Boston%2C%20MA&finish=New%20York%2C%20NY`.
3. Show `distance_miles`, `fuel_cost_usd`, `fuel_stops`, and the GeoJSON route in the response. Then show the same trip on the map UI and briefly point out `fuel/views.py`, `fuel/management/commands/load_fuel_prices.py`, and the settings that configure OSRM/Nominatim.
4. Keep the Loom under five minutes. The assessor can run the request locally after importing the provided CSV.

## Assignment checklist

- [x] Start and finish US locations
- [x] Route geometry for the map plus an interactive map page
- [x] Fuel recommendations within the 500 mile vehicle range
- [x] Cost estimate at 10 MPG
- [x] Attached CSV imported into a local indexed fuel-stop table
- [x] One routing call; no more than three uncached location/routing calls per trip
- [ ] Loom recording and GitHub publication require the applicant's own accounts and have not been performed here

