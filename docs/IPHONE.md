# Probar Vitra en un iPhone

## Qué incluye este cliente

Un contenedor UIKit/WKWebView para la interfaz actual de Vitra. Al abrirlo por primera vez pide la dirección HTTPS del servidor. Utiliza almacenamiento web persistente y permite vídeo en línea, selector de archivos y exportación de copias a través de la hoja de compartir cuando WebKit lo admite.

No contiene el servidor Python ni una copia empaquetada completa de la interfaz web. No se ha validado todavía en un iPhone físico. El audio en segundo plano, AirPlay, copias/descargas y los inicios de sesión externos necesitan validación en Safari/WebKit real. No se han agregado privilegios de audio en segundo plano para aparentar una función que aún no se ha implementado de forma nativa.

## Opción A: instalar desde Xcode

1. En un Mac, instala Xcode desde App Store y abre Xcode una vez para instalar sus componentes.
2. Instala [XcodeGen](https://github.com/yonaskolb/XcodeGen): `brew install xcodegen`.
3. Descarga o clona el repositorio y ejecuta:

```bash
cd ios
xcodegen generate --spec project.yml
open Vitra.xcodeproj
```

4. Conecta el iPhone, desbloquéalo y confía en el Mac.
5. En Xcode → Settings → Apple Accounts, añade tu cuenta. En el target Vitra → Signing & Capabilities, elige tu Team y deja la firma automática activada. Cambia el Bundle Identifier si tu equipo requiere uno propio.
6. Selecciona el iPhone como destino y pulsa Run. Activa Developer Mode en el iPhone si el sistema lo solicita.
7. Abre Vitra e introduce la URL HTTPS de tu servidor.

Una Personal Team permite pruebas con las restricciones de Apple; no equivale a una firma permanente.

## Opción B: IPA para Sideloadly

### Crear el archivo

En GitHub, **Actions → Build iPhone preview → Run workflow**. También se compila al cambiar el proyecto iOS, su script o ese workflow en `main`. Este trabajo usa un runner macOS y consume la cuota de GitHub Actions; consulta tus límites antes de repetirlo.

Después de una compilación correcta:

- **Releases → Vitra 0.2.0 · iPhone preview** contiene `Vitra-unsigned.ipa` y su SHA-256.
- **Actions → ejecución → Artifacts** contiene una copia temporal del mismo paquete.
- Una ejecución fallida no produce una IPA utilizable.

### Instalar

1. Descarga la IPA y, si quieres verificarla, compara su SHA-256 con el archivo adjunto.
2. En tu Mac, abre [Sideloadly](https://sideloadly.io/) y conecta el iPhone.
3. Selecciona el dispositivo y arrastra `Vitra-unsigned.ipa` a Sideloadly.
4. Completa la firma desde Sideloadly con tu propia cuenta de Apple. No compartas credenciales por chat ni las guardes en el repositorio.
5. Completa los pasos de confianza y Developer Mode que indique iOS y abre Vitra.

**El archivo no viene firmado.** Sideloadly debe firmarlo para tu dispositivo. La duración de esa firma depende del tipo de cuenta y de las condiciones de Apple; descargar una IPA no evita renovaciones.

### Compilar sin GitHub

Desde la raíz del repositorio en el Mac:

```bash
bash scripts/build-ios.sh
```

El resultado estará en `dist/Vitra-unsigned.ipa`.

## Dirección del servidor

- Usa `https://tu-servicio.onrender.com/` o tu dominio HTTPS propio.
- No uses `http://127.0.0.1:4203/`: en el iPhone apunta al propio teléfono.
- No escribas claves o credenciales dentro de la URL.
- El servidor debe estar en la raíz del dominio, no detrás de un prefijo como `/vitra/`.
- Si alojas en tu PC, esta debe permanecer encendida y accesible por HTTPS.

La dirección se recuerda en el dispositivo. Un cambio de dominio implica otro origen de almacenamiento: crea una copia antes de migrar. Si cambias de servidor y necesitas reiniciar la configuración del contenedor, utiliza un error de conexión para volver al formulario; desinstalar borra datos de la app y debe ser el último recurso después de una copia.

## Lista de pruebas en dispositivo

- Abrir y cerrar la app conservando la biblioteca.
- Buscar un artista, abrir álbum y reproducir la canción correcta.
- Pausar, adelantar, cambiar de canción y bloquear la pantalla.
- Confirmar si el audio continúa al cambiar de aplicación; no está garantizado en este contenedor.
- Probar el selector AirPlay en hardware compatible.
- Descargar una canción y reproducirla después de desconectar la red, manteniendo abierta la interfaz.
- Comprobar por separado el arranque en frío sin Internet: el contenedor depende del servidor para cargar la interfaz.
- Crear y restaurar una copia, guardar una portada e importar un archivo.
- Comprobar que los enlaces de autorización externa vuelven correctamente; la importación oficial requiere configuración y su flujo WebKit todavía no está validado.
