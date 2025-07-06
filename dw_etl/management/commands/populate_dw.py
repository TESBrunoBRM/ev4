# dw_etl/management/commands/populate_dw.py
import requests
from datetime import datetime, date
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from dw_etl.models import DimFecha, DimPais, DimIndicadorEconomico, DimFuenteDatos, HechosEconomicos

class Command(BaseCommand):
    help = 'Extrae datos económicos históricos de World Bank API según las especificaciones de país.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Iniciando proceso ETL con World Bank API para datos históricos...'))

        WORLD_BANK_API_BASE_URL = 'https://api.worldbank.org/v2/country'

        # Países de interés (usando códigos ISO 3166-1 alpha-3)
        # 'historical_years': 'all' para toda la data histórica disponible de la API
        # 'historical_years': N para los últimos N años
        PAISES_INTERES = [
            {'name': 'Chile', 'iso': 'CHL', 'historical_years': 'all'},
            {'name': 'Argentina', 'iso': 'ARG', 'historical_years': 10},
            {'name': 'Brasil', 'iso': 'BRA', 'historical_years': 10},
            {'name': 'México', 'iso': 'MEX', 'historical_years': 10},
            {'name': 'Colombia', 'iso': 'COL', 'historical_years': 10},
            {'name': 'Perú', 'iso': 'PER', 'historical_years': 10},
            {'name': 'Estados Unidos', 'iso': 'USA', 'historical_years': 10},
            {'name': 'Canadá', 'iso': 'CAN', 'historical_years': 10},
            {'name': 'Alemania', 'iso': 'DEU', 'historical_years': 10},
            {'name': 'España', 'iso': 'ESP', 'historical_years': 10},
            {'name': 'Japón', 'iso': 'JPN', 'historical_years': 10},
            {'name': 'China', 'iso': 'CHN', 'historical_years': 10},
            {'name': 'Reino Unido', 'iso': 'GBR', 'historical_years': 10},
            {'name': 'Australia', 'iso': 'AUS', 'historical_years': 10},
            {'name': 'India', 'iso': 'IND', 'historical_years': 10},
            {'name': 'Sudáfrica', 'iso': 'ZAF', 'historical_years': 10},
            {'name': 'Francia', 'iso': 'FRA', 'historical_years': 10},
            {'name': 'Italia', 'iso': 'ITA', 'historical_years': 10},
            {'name': 'Rusia', 'iso': 'RUS', 'historical_years': 10},
            {'name': 'Suiza', 'iso': 'CHE', 'historical_years': 10},
            {'name': 'Suecia', 'iso': 'SWE', 'historical_years': 10},
            {'name': 'Noruega', 'iso': 'NOR', 'historical_years': 10},
            {'name': 'Dinamarca', 'iso': 'DNK', 'historical_years': 10},
            {'name': 'Finlandia', 'iso': 'FIN', 'historical_years': 10},
            {'name': 'Países Bajos', 'iso': 'NLD', 'historical_years': 10},
            {'name': 'Bélgica', 'iso': 'BEL', 'historical_years': 10},
            {'name': 'Portugal', 'iso': 'PRT', 'historical_years': 10},
            {'name': 'Grecia', 'iso': 'GRC', 'historical_years': 10},
            {'name': 'Turquía', 'iso': 'TUR', 'historical_years': 10},
            {'name': 'Arabia Saudita', 'iso': 'SAU', 'historical_years': 10},
        ]

        # Rango global de años para buscar datos en la API del Banco Mundial
        # La API del Banco Mundial suele tener datos desde 1960
        GLOBAL_MIN_YEAR_API = 1960
        GLOBAL_MAX_YEAR_API = datetime.now().year # Año actual

        # Definición de los indicadores y sus códigos en World Bank API
        INDICADORES = {
            'Inflación': {
                'wb_code': 'FP.CPI.TOTL.ZG', # Índice de Precios al Consumidor (IPC), crecimiento anual %
                'unidad': '%'
            },
            'Crecimiento PIB': {
                'wb_code': 'NY.GDP.MKTP.KD.ZG', # Crecimiento anual del PIB (%)
                'unidad': '%'
            },
            'Tipo de Cambio Dólar': {
                'wb_code': 'PA.NUS.FCRF', # Tasa de cambio oficial (moneda local por USD)
                'unidad': 'Moneda Local/USD'
            },
            'IPC': { # Si lo quieres como índice base, no como crecimiento anual
                'wb_code': 'FP.CPI.TOTL', # Índice de Precios al Consumidor (base 2010=100)
                'unidad': 'Índice'
            }
        }

        # Inicializar dimensiones que no dependen de la API
        for nombre, info in INDICADORES.items():
            indicador, created = DimIndicadorEconomico.objects.get_or_create(
                nombre_indicador=nombre,
                defaults={
                    'descripcion_indicador': f'Datos de {nombre} de World Bank API',
                    'unidad_medida': info['unidad']
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Indicador {nombre} creado.'))

        fuente, created = DimFuenteDatos.objects.get_or_create(
            nombre_fuente='World Bank API',
            defaults={
                'url_fuente': 'https://data.worldbank.org/indicator',
                'fecha_ultima_actualizacion': date.today()
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('Fuente de datos World Bank API creada.'))

        # Iterar sobre todos los años posibles para poblar DimFecha (para todo el rango histórico)
        self.stdout.write(self.style.HTTP_INFO('Poblando DimFecha para el rango histórico...'))
        for year in range(GLOBAL_MIN_YEAR_API, GLOBAL_MAX_YEAR_API + 1):
            fecha_obj = date(year, 1, 1)
            DimFecha.objects.get_or_create(
                fecha_completa=fecha_obj,
                defaults={
                    'dia': fecha_obj.day,
                    'mes': fecha_obj.month,
                    'nombre_mes': fecha_obj.strftime('%B'),
                    'trimestre': (fecha_obj.month - 1) // 3 + 1,
                    'anio': fecha_obj.year,
                    'semana_del_anio': fecha_obj.isocalendar()[1],
                    'es_fin_de_semana': fecha_obj.weekday() >= 5
                }
            )
        self.stdout.write(self.style.HTTP_INFO('DimFecha poblada.'))


        # Iterar sobre países para extraer datos históricos
        for pais_data in PAISES_INTERES:
            pais_iso = pais_data['iso']
            pais_nombre = pais_data['name']
            historical_years_setting = pais_data['historical_years']

            self.stdout.write(self.style.MIGRATE_HEADING(f'Procesando datos para {pais_nombre} ({pais_iso})...'))

            dim_pais, created = DimPais.objects.get_or_create(
                codigo_iso=pais_iso,
                defaults={
                    'nombre_pais': pais_nombre,
                    'continente': 'N/A', # Estos campos podrían poblarse de otra fuente
                    'region': 'N/A',
                    'capital': 'N/A'
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'País {pais_nombre} creado.'))

            # Determinar el rango de años para este país
            if historical_years_setting == 'all':
                start_year_for_country = GLOBAL_MIN_YEAR_API
            else: # Asumimos un número de años
                start_year_for_country = max(GLOBAL_MIN_YEAR_API, GLOBAL_MAX_YEAR_API - historical_years_setting + 1)
            
            # Iterar sobre los años relevantes para este país, desde el más reciente hacia atrás
            for year_to_fetch in range(GLOBAL_MAX_YEAR_API, start_year_for_country - 1, -1):
                # Obtener la DimFecha para el año actual de la iteración
                dim_fecha_actual, _ = DimFecha.objects.get_or_create(fecha_completa=date(year_to_fetch, 1, 1))

                for indicador_nombre, indicador_info in INDICADORES.items():
                    dim_indicador = DimIndicadorEconomico.objects.get(nombre_indicador=indicador_nombre)
                    value_found = None

                    try:
                        url = f"{WORLD_BANK_API_BASE_URL}/{pais_iso}/indicator/{indicador_info['wb_code']}?date={year_to_fetch}&format=json"
                        response = requests.get(url)
                        response.raise_for_status()
                        data = response.json()

                        if data and len(data) > 1 and data[1] and data[1]:
                            value_entry = data[1][0]
                            if value_entry and value_entry.get('value') is not None:
                                value_found = value_entry['value']
                                # self.stdout.write(self.style.SUCCESS(f'  -> Dato de {indicador_nombre} para {pais_nombre} encontrado en {year_to_fetch}.'))
                        
                        if value_found is not None:
                            try:
                                with transaction.atomic():
                                    hecho, created = HechosEconomicos.objects.update_or_create(
                                        id_fecha=dim_fecha_actual, # Usar la DimFecha del año real del dato
                                        id_pais=dim_pais,
                                        id_indicador=dim_indicador,
                                        id_fuente=fuente,
                                        defaults={
                                            'porcentaje_inflacion': float(value_found) if indicador_nombre == 'Inflación' else None,
                                            'variacion_pib_anual': float(value_found) if indicador_nombre == 'Crecimiento PIB' else None,
                                            'tipo_cambio_usd_local_promedio_cierre': float(value_found) if indicador_nombre == 'Tipo de Cambio Dólar' else None,
                                            'ipc_o_devaluacion': float(value_found) if indicador_nombre == 'IPC' else None,
                                        }
                                    )
                                    if created:
                                        self.stdout.write(self.style.SUCCESS(f'Hecho insertado: {pais_nombre} - {indicador_nombre} - Año: {year_to_fetch}'))
                                    # else:
                                    #     self.stdout.write(self.style.NOTICE(f'Hecho actualizado: {pais_nombre} - {indicador_nombre} - Año: {year_to_fetch}'))

                            except Exception as e:
                                self.stdout.write(self.style.ERROR(f'Error al guardar el hecho para {pais_nombre} - {indicador_nombre} - Año: {year_to_fetch}: {e}'))
                        # else:
                        #     self.stdout.write(self.style.WARNING(f'No se encontró dato para {indicador_nombre} en {pais_nombre} para el año {year_to_fetch}.'))

                    except requests.exceptions.RequestException as e:
                        # self.stdout.write(self.style.WARNING(f'Error de red o HTTP para {pais_nombre} - {indicador_nombre} - {year_to_fetch}: {e}'))
                        pass # Ignorar para no llenar la consola de advertencias si un año no tiene datos

                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Error inesperado para {pais_nombre} - {indicador_nombre} - {year_to_fetch}: {e}'))

        self.stdout.write(self.style.SUCCESS('Proceso ETL completado exitosamente con World Bank API.'))
