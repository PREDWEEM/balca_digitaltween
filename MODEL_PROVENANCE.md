# Proveniencia del motor científico

La capa biofísica y los activos neuronales provienen del repositorio
[`PREDWEEM/LOLIUM_BAL2026`](https://github.com/PREDWEEM/LOLIUM_BAL2026).
La revisión utilizada para crear este gemelo corresponde al commit operativo:

`e08e51470d34059a5367eb21efc6c6faf1398e6e`

El repositorio fuente no fue modificado. Los hashes SHA-256 verifican que los
pesos y el clasificador copiados no fueron alterados:

| Activo | SHA-256 |
|---|---|
| `models/IW.npy` | `8614f90cd5f1337ae746690e474587b6fb22cf81652e694573cbfe4573f406d5` |
| `models/LW.npy` | `13cb012d7f4fe8e9e8399b31226e160ed60690cd4fb225a2de40375d250eb97b` |
| `models/bias_IW.npy` | `69423ba136a4caad97bed6b3aae2e7a387d87851a32eb5b2ab8de74dbcae3788` |
| `models/bias_out.npy` | `53451c25cc92da6bff25404a1e47815e38dfe58f7d83bb87c2d471298ec8a12d` |
| `models/modelo_clusters_k3.pkl` | `29f0508543bdda4b2520038c678a9df80ff9be555e0c15d5fa1f4da16a499d30` |

## Correspondencia científica

La extracción conserva:

- entradas ANN: día juliano, TMAX, TMIN y precipitación;
- coordenadas Balcarce `-37.7664, -58.2999`;
- latencia hasta JD 25;
- primer pico válido `EMERREL > 0,20`;
- termoinhibición con media móvil de cinco días y umbral 24 °C;
- choque hídrico de tres días, 45 mm, hasta JD 110;
- ET0 Hargreaves y balance hídrico superficial;
- tiempo térmico triangular 2–20–30 °C;
- ventana operativa 600–800 °Cd.

## Perfil concentrado

El núcleo incorpora directamente el decaimiento Weibull declarado en
`LOLIUM_BAL2026`:

- `tau = 3,5656 días`;
- `beta = 0,48684`;
- intensidad `0,95`;
- extinción desde 110 días pospico con remanente máximo `0,005`.

La extinción fisiológica fue incorporada en el repositorio fuente por el commit
`0c3248a82fd8434ded7d079e641de1ed6c617ed4`. En este gemelo se implementa
como código explícito y auditable en `predweem_twin/core.py`, antes de la
normalización y la asimilación.

## Componentes nuevos

La asimilación, la persistencia, el manejo de series parciales, la referencia
local, la cobertura variable y los escenarios están aislados en el paquete
`predweem_twin`. Ninguno modifica los archivos de pesos neuronales.


## Referencia Balcarce 2014 (Lolium multiflorum)

El pool local incorpora una serie semanal de *Lolium multiflorum* en Balcarce,
digitalizada de la Figura 2 de Diez de Ulzurrun P., Vigna M., Leaden M.I. y
Martino C. (2015), *Patrones de emergencia de Avena fatua (L.) y Lolium
multiflorum (Lam.) en el sudeste y sudoeste de la provincia de Buenos Aires*,
XXII Congreso ALAM / I Congreso ASACIM, 9–10/09/2015.

| Archivo | SHA-256 |
|---|---|
| `data/reference/balcarce_2014_diez_de_ulzurrun_2015.pdf` | `6387fd323bab021b0a13f94c853c1427bcc53ef57c7a23fa56e148f996ac7a89` |
| `data/reference/balcarce_2014_weekly.csv` | `031872721985144e7af556e00546cabb54d56cc2f5ea7fd5560767a66c340e40` |
| `A872824_3.xls` (SIGA, no incluido; extracto en `balcarce_2014_weather.csv`) | `516c123361ff257ebc58911c61c9817dea065ee832ac09b908030411e48dde6c` |

- Es una digitalización de un gráfico vectorial (precisión de décimas de punto
  porcentual), no la tabla original. Conviene reemplazarla por la tabla de los
  autores cuando esté disponible.
- Su unidad es **porcentaje semanal del total anual**, no plantas/m². Por eso
  entra al pool como progreso acumulado, con igual peso que las demás campañas.
- **No tiene cero inicial.** Comienza el 10/03 con 18,1 % del total; no se infiere
  ausencia previa de emergencia.
- La especie se verificó contra la serie de *Avena fatua* del mismo gráfico
  (leyenda, página, porcentajes del texto y forma de la curva). El cargador
  falla si cambia la especie, el hash o la forma temporal.
- Se habilita desde el 10/09/2015, fecha de presentación del trabajo.
- La meteorología SIGA 2014 no es entrada del modelo; tiene un hueco del 16 al
  20/03/2014. Se conserva sólo como respaldo.
- La curva sin etiquetar `2014.xlsx` del archivo `modelo_clusters_k3.pkl`
  permanece excluida: no se pudo vincular a esta serie publicada.
- En Balcarce la mediana del pool define el denominador de la normalización
  parcial; incorporar 2014 modifica los porcentajes mostrados en cortes de
  otoño (ver README) aunque no cambie los parámetros calibrados.
