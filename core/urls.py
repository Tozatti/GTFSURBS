from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('roteirizador/', views.route_planner, name='route_planner'),
    path('api/routes/', views.api_routes, name='api_routes'),
    path('api/routes/<str:route_id>/', views.api_route_detail, name='api_route_detail'),
    path('api/routes/<str:route_id>/shape/', views.api_route_shape, name='api_route_shape'),
    path('api/routes/<str:route_id>/stops/', views.api_route_stops, name='api_route_stops'),
    path('api/stops/', views.api_stops, name='api_stops'),
    path('api/stops/<str:stop_id>/', views.api_stop_detail, name='api_stop_detail'),
    path('api/stops/<str:stop_id>/times/', views.api_stop_times, name='api_stop_times'),
    path('api/search/', views.api_search, name='api_search'),
    path('api/route/plan/', views.api_plan_route, name='api_plan_route'),
]
