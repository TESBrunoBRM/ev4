# dw_etl/urls.py (¡Este es un NUEVO archivo que debes crear!)
# dw_etl/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('', views.dashboard_view, name='home'),
    path('export/excel/', views.export_economic_data_excel, name='export_excel'),
    path('export/json/', views.export_economic_data_json, name='export_json'), # Nueva URL para JSON
]
