from django.urls import path
from fuel.views import index, route_api

urlpatterns = [path("", index, name="home"), path("api/route/", route_api, name="route-api")]

