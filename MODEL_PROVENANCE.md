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

