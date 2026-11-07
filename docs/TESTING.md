# Validación antes de publicar

## Comprobaciones locales

```bash
python scripts/check.py
```

El script valida sintaxis Python, comprobaciones básicas de letras e importación, sintaxis JavaScript mediante Node y `/healthz` en un proceso local. No descarga canciones ni accede a bibliotecas personales.

## Revisión funcional

- Inicio nuevo sin datos de otra persona; recomendaciones después de escuchar.
- Búsqueda mientras se escribe; perfiles, álbumes, portadas y banners.
- Reproducción inicial y cambios rápidos, pausa, saltos, volumen, repetir y aleatorio.
- Reproducir después y continuación al terminar una playlist.
- Letras disponibles/no disponibles, tiempos reales/estimados y volver tocando la portada.
- Crear playlist, cambiar portada, añadir sugerencias y comprobar duplicados.
- Copia de seguridad y restauración en un perfil de prueba.
- Descargas, borrado y reproducción sin red.
- Temporizador y persistencia de ajustes.
- Barra compacta/completa, desplazamiento horizontal y tamaños de 320–430 px.
- Accesibilidad: teclado, etiquetas y reducir movimiento.

## iPhone

La compilación en GitHub Actions confirma que el proyecto compila; no demuestra que audio en segundo plano, AirPlay o almacenamiento funcionen en un iPhone real. Sigue la lista de `IPHONE.md` antes de distribuirlo a otras personas.
