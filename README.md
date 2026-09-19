# PREDWEEM Digital Twin — Lolium Balcarce

Gemelo digital agronómico para la dinámica de emergencia de *Lolium
multiflorum* en Balcarce, provincia de Buenos Aires.

El proyecto deriva del motor científico
[`PREDWEEM/LOLIUM_BAL2026`](https://github.com/PREDWEEM/LOLIUM_BAL2026),
que se mantiene intacto. Este repositorio agrega una capa independiente de
estado, asimilación de observaciones, persistencia por lote, pronóstico a siete
días y simulación de escenarios.

## Arquitectura

```mermaid
flowchart TD
    A["SIGA Balcarce / ECMWF / Open-Meteo"] --> B["ANN + filtros biofísicos"]
    B --> C["Agotamiento pospico Balcarce"]
    C --> D["Trayectoria diaria base"]
    E["Flujos observados"] --> F["Asimilación secuencial"]
    D --> I["Calibración local opcional"]
    I --> F
    F --> G["Estado actualizado"]
    G --> H["Pronóstico y escenarios 7 días"]
```

## Perfil concentrado de Balcarce

La ANN utiliza las cuatro entradas originales: día juliano, TMAX, TMIN y
precipitación. Después de los filtros térmico e hídrico se aplica el perfil
local:

- coordenadas de referencia: `-37.7664, -58.2999`;
- latencia inicial hasta JD 25;
- primer pico válido cuando `EMERREL > 0,20`;
- termoinhibición con media móvil de cinco días y umbral de 24 °C;
- choque hídrico de tres días, 45 mm, hasta JD 110;
- decaimiento Weibull pospico con `tau=3,5656 días`, `beta=0,48684` e
  intensidad `0,95`;
- extinción de la cohorte desde 110 días pospico cuando el remanente Weibull es
  menor o igual a `0,005`;
- ventana fenológica sombreada entre 600 y 800 °Cd.

El agotamiento se aplica antes del acumulado y antes de la asimilación. Así, las
observaciones actualizan el estado y el potencial del lote sin volver a
ensanchar la cola del perfil Balcarce.

## Referencia estacional local

El clasificador histórico común contiene campañas de varias localidades. Para
normalizar una campaña meteorológica parcial, este gemelo selecciona únicamente
las curvas cuyo nombre identifica a Balcarce.

La versión inicial dispone de una campaña local dentro del archivo histórico.
Por eso su mediana permite evitar que el último día del pronóstico se interprete
como 100 %, pero P10 y P90 todavía son preliminares. Deben incorporarse nuevas
campañas independientes para estimar incertidumbre histórica local.

## Asimilación de observaciones

Los conteos en plantas/m² se interpretan como flujo ocurrido entre dos fechas
de muestreo:

\[
Y_i = N \sum_{d=t_{i-1}+1}^{t_i} e_d
\]

donde `Y_i` es el flujo observado, `e_d` el flujo diario de PREDWEEM y `N`
el potencial estacional latente. El gemelo estima `N` sin tratar una serie
parcial como si estuviera completa.

La corrección usa una ganancia escalar:

\[
K = \frac{P}{P+R}, \qquad x^+ = x^- + K(y-x^-)
\]

Después de cada observación, la trayectoria futura se reancla sobre la fracción
remanente del perfil concentrado. La asimilación no recalibra automáticamente
los pesos de la ANN ni los parámetros Weibull.

## Calibración por sitio con datos de 2026

Se incorporó la misma capa externa de Bordenave, **ajustada con los datos y
el motor de Balcarce**. La pestaña **Calibración por sitio** conserva los
conteos, muestra el ajuste y la evaluación temporal, y permite descargar los
datos originales en CSV. Los coeficientes de Bordenave no se transfirieron.

El archivo `VALIDA (1) (4).xlsx`, hoja `Hoja1`, contiene **18 fechas** entre
el 12/03 y el 15/08/2026, en formato `FECHA + PLM2`, sin repeticiones. El
registro inicial de cero delimita el primer intervalo de ocho días hasta el
20/03, con 6300 plantas/m². Se ajustan los **17 intervalos reales**, de 5 a
16 días, sin crear observaciones diarias interpoladas. El total registrado
es **8280 plantas/m²**; no se declara que la campaña haya finalizado ni se
transfiere ese total como potencial de otros lotes.

La serie meteorológica fija abarca **227 días, del 01/01 al 15/08/2026**:
221 observados SIGA Balcarce y 6 provisionales ECMWF histórico. Contiene
TMAX, TMIN, precipitación y procedencia. La meteorología operativa sigue
actualizándose por separado y no modifica automáticamente el perfil.

La transformación es la misma que en Bordenave:

\[
F_{local}=\operatorname{logistic}(a+b\operatorname{logit}(F_{base})).
\]

Se ajustan dos parámetros mediante una búsqueda acotada y regularizada hacia
la identidad (`a ∈ [-1.5, 1.5]`, `b ∈ [0.6, 1.6]`). Cada curva se escala al
total de la ventana muestreada para comparar flujos por intervalo. Esa escala
es auxiliar y no constituye una estimación transferible del potencial.
Al no haber repeticiones, todos los intervalos utilizan el mismo piso de
ponderación: 10 % del máximo flujo observado, **630 plantas/m²**. No se
presenta ese valor como error estándar de muestreo; la columna de error
estándar se deja vacía.

La calibración conserva los pesos de la ANN, los filtros térmicos e hídricos,
el decaimiento Weibull, la extinción de la cohorte y el reloj de 600–800 °Cd.
No crea flujo donde la curva base está detenida. Se usan los valores de la
interfaz local: **cobertura 10 % y Wmax 10 mm**, y la referencia histórica
`emererel2025 balcarce.xlsx`. El archivo de campo no informa cobertura ni
manejo; cambiar esas condiciones en la interfaz no valida la transferencia
del ajuste a ellas.

### Resultados y uso

El RMSE sobre los 17 intervalos usados para ajustar pasa de **409,21 a
87,68 plantas/m²**. El perfil final tiene `a=0,65`, `b=1,425`, sin alcanzar
los límites permitidos. Es ajuste retrospectivo sobre una sola campaña.

En tres evaluaciones temporales, ajustadas con datos hasta cada corte y
evaluadas en el intervalo siguiente, el RMSE pasa de **3,93 a 5,36 plantas/m²**:
dos intervalos empeoran y uno permanece igual. Los tres son posteriores al
pico principal y sólo evalúan flujos pequeños. Se utiliza meteorología
observada/provisional, no pronósticos archivados. No se ha demostrado una
mejora predictiva ni transferencia entre años.

Por ese resultado, **Usar calibración local 2026 inicia desactivado**. Puede
activarse en la barra lateral para comparar. La capa se integra antes de la
asimilación, en los escenarios y en la exportación auditable, con estos controles:

- sólo se aplica si se selecciona la localidad Balcarce;
- no utiliza el perfil al consultar fechas anteriores al 15/08/2026;
- si se asimilan conteos de la campaña 2026, conserva la base original para
  evitar reutilizar esa campaña como calibración y nueva evidencia;
- admite asimilar conteos de campañas posteriores sobre el perfil local;
- un cambio del motor, pesos o referencia invalida la huella del perfil;
- conserva separadas las curvas base, calibrada y asimilada.

Los conteos de referencia no se insertan automáticamente en SQLite ni
sobrescriben observaciones guardadas. Para asimilarlos en un lote, descargue
el CSV desde la pestaña y cárguelo en **Observaciones**. El cierre meteorológico
del 01/10/2026 se mantiene; una campaña posterior requiere configurar su
meteorología. El perfil fue preparado el 19/09/2026, por lo que las consultas
retrospectivas de 2026 no se presentan como pronósticos históricos reales.

### Reproducción y trazabilidad

```bash
python scripts/calibrate_site.py
python -m pytest -q
```

Las entradas y salidas se conservan en `data/calibration/`: conteos,
meteorología fija, procedencia, perfil JSON, ajuste por intervalos y evaluación
temporal. Se registran hashes del archivo adjunto, los datos y el modelo.
El identificador del perfil distingue revisiones aun si conservan la última
fecha de muestreo. El script no descarga meteorología ni reentrena la ANN.

## Datos admitidos

La pestaña **Observaciones** acepta CSV, TSV, XLS o XLSX con:

| Estructura | Interpretación |
|---|---|
| `FECHA + PLM2` | Flujo de plantas/m² por intervalo |
| `FECHA + EMERGENCIA_ACUMULADA` | Acumulado 0–1 o 0–100 % |
| `Fecha + 1 + 2 + 3 + media(SR).m2` | Tres repeticiones y media por m² |
| `FECHA + COBERTURA_PCT` | Cobertura variable del rastrojo |

Emergencia y cobertura pueden estar en el mismo archivo. Las observaciones y
mediciones guardadas pueden borrarse desde la interfaz.

Cuando existen tres repeticiones, la incertidumbre se estima desde su error
estándar, con un mínimo de 5 % para representar variación no capturada por los
cuadrantes.

## Meteorología operativa

La fuente primaria es SIGA–INTA Balcarce, estación `A872824`. Los huecos
vencidos se completan provisionalmente con ECMWF IFS histórico y son
reemplazados cuando SIGA publica el dato. Desde la fecha actual se utilizan
siete días de ECMWF IFS ENS 0,25° y el percentil 50 de temperatura y
precipitación.

También se admite Open-Meteo georreferenciado o un archivo meteorológico
cargado por el usuario.

## Funciones

- estado persistente e independiente por lote;
- meteorología observada hasta la fecha del estado y pronóstico a siete días;
- flujo diario mostrado con barras azules;
- curva PREDWEEM base frente al estado actualizado;
- potencial estacional automático u opcionalmente informado;
- cobertura constante o serie observada interpolada;
- escenarios de lluvia y temperatura;
- hitos d25, d50, d75 y d95;
- ventana fenológica 600–800 °Cd;
- auditoría de innovaciones, incertidumbres y ganancias;
- exportación CSV de la trayectoria completa.

## Ejecución local

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

En Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
streamlit run app.py
```

## Pruebas

```bash
python -m pytest -q
```

Las pruebas cubren los límites biofísicos, el decaimiento y la extinción de la
cohorte, la referencia local, la asimilación, la cobertura variable, la
persistencia y los escenarios.

## Alcance

Esta es una versión MVP experimental. La referencia estacional local y la capa
de asimilación deben validarse prospectivamente con campañas independientes
antes de establecer precisión operativa. PREDWEEM es soporte para decisión y no
reemplaza el monitoreo del lote ni el criterio profesional responsable.

## Autoría

**PREDWEEM by Guillermo R. Chantre**

Consulte [COPYRIGHT.md](COPYRIGHT.md) y
[MODEL_PROVENANCE.md](MODEL_PROVENANCE.md).

## Cierre meteorológico de la campaña 2026

La serie operativa termina el **1 de octubre de 2026, inclusive**. El límite
se aplica a SIGA, al puente provisional, al pronóstico ECMWF, a la consulta
Open-Meteo y a los archivos cargados en la aplicación. Después del cierre,
las actualizaciones pueden completar o reemplazar datos provisionales por
observaciones hasta esa fecha, sin agregar días posteriores ni exigir
pronósticos futuros. La interfaz reduce el horizonte esperado al acercarse
al cierre. Las referencias históricas de emergencia mantienen su extensión.
