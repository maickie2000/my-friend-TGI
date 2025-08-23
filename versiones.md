## My Friend TGI - v1.2 CÁSCARA GUI

- Se agregó barra de menú con acciones básicas: Archivo, Ayuda
- Organización en pestañas para módulos: Excel, Flow 2D
- Preparación para agregar barra de herramientas (toolbar)
- Código estructurado con buenas prácticas (docstrings, pylint, pyright)
## My Friend TGI - v1.3 VISUAL & EXPORT

- Mejoras en el módulo XSECI:
  - Leyenda reubicada debajo del eje X (mejor UX).
  - Escala 1:1 ajustable con eje X desde 0 y control dinámico del rango Y.
  - Exportación a PNG con nombre por defecto detallado (Sección + Tiempo).
  - Exportación por lotes con nombres únicos para evitar sobrescribir archivos.
  - DPI configurable y opción de copiar la gráfica al portapapeles.
- Soporte para navegación rápida:
  - Botones ⏮ / ⏭ para cambiar tiempos.
  - Atajos de teclado `Ctrl+←/→` para navegar entre secciones.
  - Atajo `0` para resetear vista.
- Preparación para barra de progreso en cargas pesadas (parseo XSECI).
- Refactor de `_plot_profile` para código más claro y mantenible.
