# dw_etl/views.py
from django.shortcuts import render
from django.db.models import F, Case, When, Value, DecimalField
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Font, Border, Side, Alignment, PatternFill
from openpyxl.utils import get_column_letter

from .models import HechosEconomicos, DimPais, DimIndicadorEconomico, DimFecha

def dashboard_view(request):
    """
    Vista para mostrar un dashboard con los datos económicos más recientes
    para todos los países y realizar un análisis comparativo.
    """
    # Recuperar los objetos de indicadores económicos
    try:
        inflacion_indicador = DimIndicadorEconomico.objects.get(nombre_indicador='Inflación')
        pib_indicador = DimIndicadorEconomico.objects.get(nombre_indicador='Crecimiento PIB')
        tipo_cambio_indicador = DimIndicadorEconomico.objects.get(nombre_indicador='Tipo de Cambio Dólar')
        ipc_indicador = DimIndicadorEconomico.objects.get(nombre_indicador='IPC')
    except DimIndicadorEconomico.DoesNotExist:
        return render(request, 'dw_etl/dashboard.html', {'error_message': 'Uno o más indicadores económicos no se encontraron en la base de datos. Por favor, asegúrate de que el comando populate_dw se ejecutó correctamente.'})

    # Obtener la DimFecha para el año de referencia (2025), que es donde se almacenan los hechos
    try:
        fecha_referencia = DimFecha.objects.get(anio=2025)
    except DimFecha.DoesNotExist:
        return render(request, 'dw_etl/dashboard.html', {'error_message': 'No se encontró la DimFecha para el año 2025 en la base de datos. Por favor, ejecuta el comando populate_dw.'})

    # Preparar un diccionario para almacenar los datos por país
    dashboard_data_dict = {}
    for pais in DimPais.objects.all().order_by('nombre_pais'):
        dashboard_data_dict[pais.nombre_pais] = {
            'nombre_pais': pais.nombre_pais,
            'iso': pais.codigo_iso,
            'inflacion': None,
            'pib_crecimiento': None,
            'tipo_cambio': None,
            'ipc': None,
            'anio_dato_inflacion': 'N/D',
            'anio_dato_pib': 'N/D',
            'anio_dato_tipo_cambio': 'N/D',
            'anio_dato_ipc': 'N/D',
        }

    # Recuperar todos los hechos económicos para el año de referencia (2025)
    # y agruparlos por país e indicador
    hechos = HechosEconomicos.objects.filter(id_fecha=fecha_referencia).select_related('id_pais', 'id_indicador')

    for hecho in hechos:
        pais_nombre = hecho.id_pais.nombre_pais
        indicador_nombre = hecho.id_indicador.nombre_indicador

        if pais_nombre in dashboard_data_dict:
            if indicador_nombre == 'Inflación':
                dashboard_data_dict[pais_nombre]['inflacion'] = hecho.porcentaje_inflacion
                dashboard_data_dict[pais_nombre]['anio_dato_inflacion'] = hecho.anio_dato_real
            elif indicador_nombre == 'Crecimiento PIB':
                dashboard_data_dict[pais_nombre]['pib_crecimiento'] = hecho.variacion_pib_anual
                dashboard_data_dict[pais_nombre]['anio_dato_pib'] = hecho.anio_dato_real
            elif indicador_nombre == 'Tipo de Cambio Dólar':
                dashboard_data_dict[pais_nombre]['tipo_cambio'] = hecho.tipo_cambio_usd_local_promedio_cierre
                dashboard_data_dict[pais_nombre]['anio_dato_tipo_cambio'] = hecho.anio_dato_real
            elif indicador_nombre == 'IPC':
                dashboard_data_dict[pais_nombre]['ipc'] = hecho.ipc_o_devaluacion
                dashboard_data_dict[pais_nombre]['anio_dato_ipc'] = hecho.anio_dato_real

    # Convertir el diccionario a una lista para pasar al template
    dashboard_data = list(dashboard_data_dict.values())

    # --- Lógica de Análisis Comparativo (para mostrar en HTML) ---
    best_inflation_country = None
    min_inflation = float('inf')

    for data in dashboard_data:
        if data['inflacion'] is not None and data['inflacion'] != 'N/D':
            try:
                current_inflation = float(data['inflacion'])
                if current_inflation < min_inflation:
                    min_inflation = current_inflation
                    best_inflation_country = data['nombre_pais']
            except ValueError:
                pass # Ignorar si el valor no es un número válido

    # Preparar el contexto para el template
    context = {
        'dashboard_data': dashboard_data,
        'current_year': fecha_referencia.anio,
        'best_inflation_country': best_inflation_country,
        'min_inflation_value': min_inflation if min_inflation != float('inf') else 'N/D',
        'historical_data_limitation_message': "Para un análisis preciso de periodos históricos (como devaluación vs. recesión o relación tipo de cambio vs. crecimiento), se necesitaría un conjunto de datos históricos más extenso (series de tiempo) y un análisis estadístico más profundo. Los datos actuales se centran en los valores más recientes disponibles.",
    }
    return render(request, 'dw_etl/dashboard.html', context)


def export_economic_data_excel(request):
    """
    Vista para exportar los datos económicos a un archivo Excel.
    """
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="datos_economicos.xlsx"'

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Datos Económicos Recientes"

    # Definir estilos
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
    border_style = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    center_aligned_text = Alignment(horizontal="center", vertical="center")

    # Encabezados de la tabla
    headers = ["País", "Código ISO", "Inflación (%)", "Año Inflación", "Crecimiento PIB (%)", "Año Crecimiento PIB", "Tipo Cambio (USD/Local)", "Año Tipo Cambio", "IPC (Índice)", "Año IPC"]
    sheet.append(headers)

    # Aplicar estilos a la fila de encabezados
    for col_num, header_title in enumerate(headers, 1):
        cell = sheet.cell(row=1, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = border_style
        cell.alignment = center_aligned_text
        sheet.column_dimensions[get_column_letter(col_num)].width = 18 # Ajustar ancho de columna

    # Obtener los datos del dashboard de manera similar a dashboard_view
    try:
        inflacion_indicador = DimIndicadorEconomico.objects.get(nombre_indicador='Inflación')
        pib_indicador = DimIndicadorEconomico.objects.get(nombre_indicador='Crecimiento PIB')
        tipo_cambio_indicador = DimIndicadorEconomico.objects.get(nombre_indicador='Tipo de Cambio Dólar')
        ipc_indicador = DimIndicadorEconomico.objects.get(nombre_indicador='IPC')
    except DimIndicadorEconomico.DoesNotExist:
        # En un escenario de exportación, esto debería manejarse mejor,
        # quizás registrando un error o devolviendo un archivo vacío con un mensaje.
        # Por ahora, asumimos que los indicadores existen.
        pass

    try:
        fecha_referencia = DimFecha.objects.get(anio=2025)
    except DimFecha.DoesNotExist:
        pass # Similar, asumir que la fecha existe

    dashboard_data_dict = {}
    for pais in DimPais.objects.all().order_by('nombre_pais'):
        dashboard_data_dict[pais.nombre_pais] = {
            'nombre_pais': pais.nombre_pais,
            'iso': pais.codigo_iso,
            'inflacion': None,
            'pib_crecimiento': None,
            'tipo_cambio': None,
            'ipc': None,
            'anio_dato_inflacion': 'N/D',
            'anio_dato_pib': 'N/D',
            'anio_dato_tipo_cambio': 'N/D',
            'anio_dato_ipc': 'N/D',
        }

    hechos = HechosEconomicos.objects.filter(id_fecha=fecha_referencia).select_related('id_pais', 'id_indicador')

    for hecho in hechos:
        pais_nombre = hecho.id_pais.nombre_pais
        indicador_nombre = hecho.id_indicador.nombre_indicador

        if pais_nombre in dashboard_data_dict:
            if indicador_nombre == 'Inflación':
                dashboard_data_dict[pais_nombre]['inflacion'] = hecho.porcentaje_inflacion
                dashboard_data_dict[pais_nombre]['anio_dato_inflacion'] = hecho.anio_dato_real
            elif indicador_nombre == 'Crecimiento PIB':
                dashboard_data_dict[pais_nombre]['pib_crecimiento'] = hecho.variacion_pib_anual
                dashboard_data_dict[pais_nombre]['anio_dato_pib'] = hecho.anio_dato_real
            elif indicador_nombre == 'Tipo de Cambio Dólar':
                dashboard_data_dict[pais_nombre]['tipo_cambio'] = hecho.tipo_cambio_usd_local_promedio_cierre
                dashboard_data_dict[pais_nombre]['anio_dato_tipo_cambio'] = hecho.anio_dato_real
            elif indicador_nombre == 'IPC':
                dashboard_data_dict[pais_nombre]['ipc'] = hecho.ipc_o_devaluacion
                dashboard_data_dict[pais_nombre]['anio_dato_ipc'] = hecho.anio_dato_real

    # Escribir los datos en la hoja de cálculo
    for data in dashboard_data_dict.values():
        row_data = [
            data['nombre_pais'],
            data['iso'],
            data['inflacion'] if data['inflacion'] is not None else 'N/D',
            data['anio_dato_inflacion'],
            data['pib_crecimiento'] if data['pib_crecimiento'] is not None else 'N/D',
            data['anio_dato_pib'],
            data['tipo_cambio'] if data['tipo_cambio'] is not None else 'N/D',
            data['anio_dato_tipo_cambio'],
            data['ipc'] if data['ipc'] is not None else 'N/D',
            data['anio_dato_ipc'],
        ]
        sheet.append(row_data)

    # Guardar el libro de trabajo en la respuesta HTTP
    workbook.save(response)
    return response
