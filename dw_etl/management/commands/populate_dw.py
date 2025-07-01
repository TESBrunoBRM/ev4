# dw_etl/management/commands/populate_dw.py
import requests
from datetime import datetime, date
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from dw_etl.models import DimFecha, DimPais, DimIndicadorEconomico, DimFuenteDatos, HechosEconomicos

class Command(BaseCommand):
    help = 'Extrae los datos económicos más recientes de World Bank API para cada país e indicador.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Iniciando proceso ETL con World Bank API (buscando el dato más reciente)...'))

        # Configuración de World Bank API
        WORLD_BANK_API_BASE_URL = 'https://api.worldbank.org/v2/country'

        # Países de interés (usando códigos ISO 3166-1 alpha-3)
        PAISES_INTERES = [
            {'name': 'Chile', 'iso': 'CHL'},
            {'name': 'Argentina', 'iso': 'ARG'},
            {'name': 'Brasil', 'iso': 'BRA'},
            {'name': 'México', 'iso': 'MEX'},
            {'name': 'Colombia', 'iso': 'COL'},
            {'name': 'Perú', 'iso': 'PER'},
            {'name': 'Estados Unidos', 'iso': 'USA'},
            {'name': 'Canadá', 'iso': 'CAN'},
            {'name': 'Alemania', 'iso': 'DEU'},
            {'name': 'España', 'iso': 'ESP'},
            {'name': 'Japón', 'iso': 'JPN'},
            {'name': 'China', 'iso': 'CHN'},
            {'name': 'Reino Unido', 'iso': 'GBR'},
            {'name': 'Australia', 'iso': 'AUS'},
            {'name': 'India', 'iso': 'IND'},
            {'name': 'Sudáfrica', 'iso': 'ZAF'},
            {'name': 'Francia', 'iso': 'FRA'},
            {'name': 'Italia', 'iso': 'ITA'},
            {'name': 'Rusia', 'iso': 'RUS'},
            {'name': 'Suiza', 'iso': 'CHE'},
            {'name': 'Suecia', 'iso': 'SWE'},
            {'name': 'Noruega', 'iso': 'NOR'},
            {'name': 'Dinamarca', 'iso': 'DNK'},
            {'name': 'Finlandia', 'iso': 'FIN'},
            {'name': 'Países Bajos', 'iso': 'NLD'},
            {'name': 'Bélgica', 'iso': 'BEL'},
            {'name': 'Portugal', 'iso': 'PRT'},
            {'name': 'Grecia', 'iso': 'GRC'},
            {'name': 'Turquía', 'iso': 'TUR'},
            {'name': 'Arabia Saudita', 'iso': 'SAU'},
        ]

        # Rango de años para buscar el dato más reciente
        # Comenzamos desde el año actual (o un poco antes si los datos son muy recientes)
        # y retrocedemos hasta un año histórico razonable para el Banco Mundial.
        MAX_YEAR_TO_SEARCH = datetime.now().year # Año actual
        MIN_YEAR_TO_SEARCH = 1960 # Año histórico para asegurar cobertura

        # Año de referencia para la DimFecha del hecho (el hecho siempre se asocia a 2025)
        ANIO_DE_REFERENCIA_PARA_HECHO = 2025

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

        # Asegurarse de que la DimFecha para el año de referencia (2025) exista
        fecha_obj_referencia = date(ANIO_DE_REFERENCIA_PARA_HECHO, 1, 1)
        dim_fecha_referencia, created = DimFecha.objects.get_or_create(
            fecha_completa=fecha_obj_referencia,
            defaults={
                'dia': fecha_obj_referencia.day,
                'mes': fecha_obj_referencia.month,
                'nombre_mes': fecha_obj_referencia.strftime('%B'),
                'trimestre': (fecha_obj_referencia.month - 1) // 3 + 1,
                'anio': fecha_obj_referencia.year,
                'semana_del_anio': fecha_obj_referencia.isocalendar()[1],
                'es_fin_de_semana': fecha_obj_referencia.weekday() >= 5
            }
        )
        if created:
            self.stdout.write(self.style.HTTP_INFO(f'DimFecha para el año de referencia {ANIO_DE_REFERENCIA_PARA_HECHO} creada.'))


        # Iterar sobre países para extraer datos
        for pais_data in PAISES_INTERES:
            pais_iso = pais_data['iso']
            pais_nombre = pais_data['name']

            self.stdout.write(self.style.MIGRATE_HEADING(f'Procesando datos para {pais_nombre} ({pais_iso})...'))

            dim_pais, created = DimPais.objects.get_or_create(
                codigo_iso=pais_iso,
                defaults={
                    'nombre_pais': pais_nombre,
                    'continente': 'N/A',
                    'region': 'N/A',
                    'capital': 'N/A'
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'País {pais_nombre} creado.'))

            for indicador_nombre, indicador_info in INDICADORES.items():
                dim_indicador = DimIndicadorEconomico.objects.get(nombre_indicador=indicador_nombre)
                value_found = None
                anio_dato_real_found = None

                # Iterar hacia atrás desde el año más reciente hasta el más antiguo
                for year_to_fetch in range(MAX_YEAR_TO_SEARCH, MIN_YEAR_TO_SEARCH - 1, -1):
                    try:
                        url = f"{WORLD_BANK_API_BASE_URL}/{pais_iso}/indicator/{indicador_info['wb_code']}?date={year_to_fetch}&format=json"
                        response = requests.get(url)
                        response.raise_for_status()
                        data = response.json()

                        if data and len(data) > 1 and data[1] and data[1]:
                            value_entry = data[1][0]
                            if value_entry and value_entry.get('value') is not None:
                                value_found = value_entry['value']
                                anio_dato_real_found = int(value_entry.get('date', '0'))
                                self.stdout.write(self.style.SUCCESS(f'  -> Dato de {indicador_nombre} para {pais_nombre} encontrado en {anio_dato_real_found}.'))
                                break # Salir del bucle de años si se encuentra un dato
                        
                    except requests.exceptions.RequestException as e:
                        # self.stdout.write(self.style.WARNING(f'  -> Error de red/HTTP al buscar {indicador_nombre} para {pais_nombre} en {year_to_fetch}: {e}'))
                        pass # Ignorar errores de red/HTTP para seguir buscando en años anteriores
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'  -> Error inesperado al buscar {indicador_nombre} para {pais_nombre} en {year_to_fetch}: {e}'))
                        pass # Ignorar otros errores para seguir buscando

                if value_found is not None:
                    try:
                        with transaction.atomic():
                            hecho, created = HechosEconomicos.objects.update_or_create(
                                id_fecha=dim_fecha_referencia, # El hecho siempre se asocia a la fecha de referencia (2025)
                                id_pais=dim_pais,
                                id_indicador=dim_indicador,
                                id_fuente=fuente,
                                defaults={
                                    'porcentaje_inflacion': float(value_found) if indicador_nombre == 'Inflación' else None,
                                    'variacion_pib_anual': float(value_found) if indicador_nombre == 'Crecimiento PIB' else None,
                                    'tipo_cambio_usd_local_promedio_cierre': float(value_found) if indicador_nombre == 'Tipo de Cambio Dólar' else None,
                                    'ipc_o_devaluacion': float(value_found) if indicador_nombre == 'IPC' else None,
                                    'anio_dato_real': anio_dato_real_found # Guardar el año real del dato
                                }
                            )
                            if created:
                                self.stdout.write(self.style.SUCCESS(f'Hecho insertado: {pais_nombre} - {indicador_nombre} - Año Dato: {anio_dato_real_found}'))
                            else:
                                self.stdout.write(self.style.NOTICE(f'Hecho actualizado: {pais_nombre} - {indicador_nombre} - Año Dato: {anio_dato_real_found}'))

                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Error al guardar el hecho para {pais_nombre} - {indicador_nombre} - Año Dato: {anio_dato_real_found}: {e}'))
                else:
                    self.stdout.write(self.style.WARNING(f'No se encontró ningún dato para {indicador_nombre} en {pais_nombre} en el rango {MIN_YEAR_TO_SEARCH}-{MAX_YEAR_TO_SEARCH}. Saltando inserción.'))

        self.stdout.write(self.style.SUCCESS('Proceso ETL completado exitosamente con World Bank API.'))
