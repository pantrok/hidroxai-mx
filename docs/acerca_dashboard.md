# Dashboard

**[Abrir el dashboard](https://pantrok.github.io/hidroxai-mx/dashboard/)**

El dashboard muestra los resultados del benchmark sin recalcularlos:

- un mapa de las 91 estaciones evaluables, coloreado por el desempeño de cada modelo;
- el hidrograma observado contra el pronóstico de cada estación, modelo y horizonte;
- los mapas de explicabilidad por cuenca;
- la línea de tiempo de alertas con sus tablas POD, FAR y CSI.

Es una aplicación de Streamlit que corre en el navegador con
[stlite](https://github.com/whitphx/stlite) (Pyodide/WebAssembly), sin servidor. La primera carga
descarga Python al navegador y puede tardar entre 15 y 30 segundos.

!!! warning "Uso"
    Pronósticos retrospectivos sobre 2023–2025 con fines de investigación; no es un sistema de
    alerta operativo.
