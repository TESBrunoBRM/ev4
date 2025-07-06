from django.db import models

class DimFecha(models.Model):
    # ID_Fecha será auto-incremento por defecto en Django
    fecha_completa = models.DateField(unique=True)
    dia = models.IntegerField()
    mes = models.IntegerField()
    nombre_mes = models.CharField(max_length=20)
    trimestre = models.IntegerField()
    anio = models.IntegerField()
    semana_del_anio = models.IntegerField()
    es_fin_de_semana = models.BooleanField()

    def __str__(self):
        return str(self.fecha_completa)

class DimPais(models.Model):
    # ID_Pais será auto-incremento por defecto en Django
    nombre_pais = models.CharField(max_length=100, unique=True)
    codigo_iso = models.CharField(max_length=3, unique=True) # ISO 3166-1 alpha-3
    continente = models.CharField(max_length=50, blank=True, null=True)
    region = models.CharField(max_length=100, blank=True, null=True)
    capital = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.nombre_pais

class DimIndicadorEconomico(models.Model):
    # ID_Indicador será auto-incremento por defecto en Django
    nombre_indicador = models.CharField(max_length=100, unique=True)
    descripcion_indicador = models.TextField(blank=True, null=True)
    unidad_medida = models.CharField(max_length=50)

    def __str__(self):
        return self.nombre_indicador

class DimFuenteDatos(models.Model):
    # ID_Fuente será auto-incremento por defecto en Django
    nombre_fuente = models.CharField(max_length=100, unique=True)
    url_fuente = models.URLField(max_length=200, blank=True, null=True)
    fecha_ultima_actualizacion = models.DateField(blank=True, null=True)

    def __str__(self):
        return self.nombre_fuente

class HechosEconomicos(models.Model):
    # ID_Hecho será auto-incremento por defecto en Django
    # id_fecha ahora apuntará al año real del dato
    id_fecha = models.ForeignKey(DimFecha, on_delete=models.CASCADE)
    id_pais = models.ForeignKey(DimPais, on_delete=models.CASCADE)
    id_indicador = models.ForeignKey(DimIndicadorEconomico, on_delete=models.CASCADE)
    id_fuente = models.ForeignKey(DimFuenteDatos, on_delete=models.CASCADE)
    porcentaje_inflacion = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    variacion_pib_anual = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    tipo_cambio_usd_local_promedio_cierre = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True)
    ipc_o_devaluacion = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    # anio_dato_real se elimina, ya que el año está en id_fecha.

    class Meta:
        # Asegura que no haya duplicados para la misma combinación de fecha, país, indicador
        # Ahora, id_fecha será el año real del dato
        unique_together = ('id_fecha', 'id_pais', 'id_indicador')

    def __str__(self):
        return f"Hecho Económico: {self.id_pais.nombre_pais} - {self.id_indicador.nombre_indicador} - {self.id_fecha.anio}"
