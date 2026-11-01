# Servidor de prueba de Vitra

Paquete separado de la instalación local. No incluye caché de audio, historial, cuentas ni credenciales. Sirve el catálogo, audio e interfaz desde el mismo origen HTTPS. La IPA todavía no está compilada ni conectada a este despliegue.

## Publicar gratis en Render

1. Crea un repositorio privado en GitHub con el CONTENIDO de esta carpeta en la raíz.
2. Inicia sesión en https://dashboard.render.com/ y conecta ese repositorio.
3. Elige New → Blueprint para usar render.yaml, o Web Service con Docker y plan Free. No selecciones servicios de pago.
4. Cuando termine el despliegue, la URL HTTPS del servicio será la dirección del servidor. /healthz debe devolver {"status":"ok"}.
5. Comprueba búsqueda, perfil de artista y reproducción de una canción nueva. La extracción de YouTube puede ser bloqueada desde direcciones de centros de datos; no se ha validado desde Render. No se garantiza que el audio funcione solo porque el servidor arranque.

El plan gratuito se suspende tras 15 minutos sin tráfico y puede tardar alrededor de un minuto en arrancar. Su caché se pierde en reinicios; las descargas del iPhone son independientes. Hay límites de transferencia y compilación. Revisa https://render.com/docs/free y mantén el despliegue dentro de la modalidad gratuita; no se configura ningún mecanismo para evitar su suspensión.

Para pruebas personales. No incorpora cuentas, autenticación ni límites por usuario. No es una entrega lista para distribución pública masiva.

## Verificación pendiente

Se comprobó la sintaxis de Python. La imagen Docker y el alojamiento real deben probarse en el despliegue. Cuando exista la dirección definitiva, se configurará el cliente iOS para usarla y se probarán búsqueda, reproducción y descarga desde un iPhone físico.
