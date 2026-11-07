## Vitra 0.2.0 · iPhone preview

Versión de prueba con la interfaz móvil renovada, biblioteca local sin cuenta y el contenedor experimental para iPhone.

### Cambios destacados
- Letras inmersivas, transiciones suaves por palabras y regreso al reproductor al tocar la portada.
- Perfiles, álbumes, portadas y banners en vídeo cuando están disponibles.
- Playlists con portada gris/disco o imagen propia, sugerencias personalizadas e historial con carátulas.
- Barra inferior con transformación fluida y sin texto del contenido superpuesto.
- Ajustes organizados: volumen, ahorro de datos, letras, continuación y temporizador.
- Carga progresiva, caché y correcciones de guardado y cambios rápidos de canción.
- README y guías de instalación, privacidad, arquitectura y pruebas.

### Archivo para iPhone
`Vitra-unsigned.ipa` se compila para dispositivo **sin firma**. Debes firmarlo con Sideloadly o compilar/firmar con Xcode. No es una instalación permanente ni una distribución App Store.

Al abrirlo pide la URL HTTPS de tu servidor de Vitra. El servidor no está incluido. Es un contenedor WKWebView, no una reescritura nativa del reproductor. La reproducción en segundo plano y el funcionamiento en iPhone físico requieren pruebas.

Las letras pueden usar tiempos estimados cuando no existen tiempos originales. La cobertura de canciones y letras depende de servicios externos. Los datos de la biblioteca se guardan por dispositivo/origen; las copias no contienen el audio descargado.
