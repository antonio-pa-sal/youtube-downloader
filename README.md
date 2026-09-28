# Video Downloader

Script de terminal en Python para descargar vídeos desde una URL. Prueba `yt-dlp`, archivos directos, streams HLS/DASH y, opcionalmente, páginas dinámicas mediante Playwright.

## Funcionalidades

- Descarga video en 1080p cuando esta disponible.
- Intenta primero `yt-dlp`, que permite trabajar con muchas plataformas además de YouTube.
- Descarga archivos directos (`.mp4`, `.webm`, `.mov`, etc.) mediante HTTP.
- Procesa streams HLS (`.m3u8`) y DASH (`.mpd`) con `ffmpeg`.
- Puede inspeccionar páginas que generan el reproductor con JavaScript usando Playwright.
- En YouTube, puede buscar pistas de doblaje automático, por ejemplo `es-US`.
- Permite usar cookies opcionales de Chrome, Firefox, Safari y otros navegadores compatibles.
- Convierte las descargas de audio independiente a MP3 con la mejor calidad disponible.
- Fusiona video y audio con `ffmpeg`.
- Genera PDFs de transcripcion:
  - con marcas temporales
  - sin marcas temporales, agrupando texto segun puntuacion
- Permite elegir PDF, Markdown (`.md`) o ambos formatos al solicitar una transcripcion.
- Si yt-dlp no encuentra una transcripcion, puede generar la original con Whisper MLX en macOS Apple silicon.

## Requisitos

- Python 3.12 recomendado.
- `ffmpeg` instalado y disponible en el `PATH`.
- Node.js instalado y disponible en el `PATH` para resolver algunos formatos de YouTube usados por `yt-dlp`.

Playwright es opcional. Para activarlo:

```bash
python -m pip install playwright
python -m playwright install chromium
```

Whisper MLX tambien es opcional y solo funciona en macOS Apple silicon. Instala el motor junto con las dependencias principales:

```bash
python -m pip install -r requirements-whisper-mlx.txt
```

La primera transcripcion descarga el modelo multilingue `whisper-small-mlx` (aprox. 481 MB). Si el motor no esta instalado, la aplicacion avisa y muestra este comando. Whisper detecta el idioma para la transcripcion original; su tarea de traduccion integrada solo produce ingles. Para otros idiomas traducidos se necesitan subtitulos traducidos disponibles.

En macOS con Homebrew:

```bash
brew install ffmpeg node
```

En Ubuntu:

```bash
sudo apt update
sudo apt install ffmpeg nodejs npm
```

En Windows:

- Instala Python desde https://www.python.org/
- Instala ffmpeg desde https://ffmpeg.org/
- Instala Node.js desde https://nodejs.org/
- Asegurate de que `python`, `ffmpeg` y `node` funcionen desde PowerShell o CMD.

## Instalacion

Clona el repositorio y crea un entorno virtual:

```bash
git clone <URL_DEL_REPOSITORIO>
cd youtube-downloader
python -m venv venv
```

Activa el entorno virtual.

macOS/Linux:

```bash
source venv/bin/activate
```

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

Instala dependencias:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Ejecucion

macOS/Linux:

```bash
SSL_CERT_FILE="$(python -m certifi)" python youtube_downloader.py
```

Windows PowerShell:

```powershell
$env:SSL_CERT_FILE = python -m certifi
python youtube_downloader.py
```

El script pedira:

- URL del vídeo o de la página que lo contiene.
- Ruta de guardado, con `Downloads` como valor por defecto.
- Idioma deseado para audio/transcripcion, con `es` como valor por defecto.
- Navegador opcional del que se leeran cookies para los respaldos de `yt-dlp`.

Si el contenido requiere inicio de sesión, contraseña o permisos especiales, introduce el navegador que contiene la sesión para que `yt-dlp` intente leer sus cookies. El programa informa cuando detecta respuestas de autenticación, acceso denegado o DRM.

Para no usar cookies, deja este ultimo campo vacio. Las cookies se leen localmente y nunca se guardan en el repositorio.

En el menu de descargas, escribe un numero para marcar o desmarcar una opcion. Usa `d` para continuar, `a` para marcar todas, `n` para limpiar la seleccion y `q` para cancelar. Tambien puedes escribir varios numeros, por ejemplo `1,3,6`.

Si eliges una transcripcion, el programa pregunta el formato: `p` para PDF, `m` para Markdown, `a` para generar ambos, o Intro para conservar el formato PDF predeterminado. El Markdown incluye titulo, idioma, fuente, enlace al video, marcas de tiempo y texto agrupado en parrafos. Las opciones del menú de transcripción generan nombres como `<titulo>_transcripcion_original.md`.

## Ejecutar desde cualquier directorio

En macOS, el comando global `python-youtubedownloader` crea el entorno virtual si falta, comprueba sus dependencias y ejecuta la aplicacion desde cualquier carpeta:

```bash
python-youtubedownloader
```

Para comprobar la instalacion sin iniciar una descarga:

```bash
python-youtubedownloader --self-test
```

El lanzador esta en [scripts/python-youtubedownloader](scripts/python-youtubedownloader) y se instala mediante un enlace en `~/.local/bin`.

## Salidas generadas

Segun disponibilidad del video, se generaran archivos como:

```text
<titulo>_1080p_original.mp4
<titulo>_1080p_es.mp4
<titulo>_audio_original.mp3
<titulo>_audio_es.mp3
<titulo>_transcripcion_original.pdf
<titulo>_transcripcion_original_sin_marcas.pdf
<titulo>_transcripcion_original.md
<titulo>_transcripcion_es.pdf
<titulo>_transcripcion_es_sin_marcas.pdf
<titulo>_transcripcion_es.md
```

## Notas importantes

- YouTube puede limitar temporalmente la descarga de subtitulos/traducciones con `HTTP Error 429: Too Many Requests`. Si ocurre, espera unos minutos y vuelve a ejecutar.
- No todos los videos ofrecen pista doblada, subtitulos o traduccion automatica.
- Si no hay subtitulos, la opcion de transcripcion original puede recurrir a Whisper MLX cuando este instalado en un Mac Apple silicon. El texto se genera automaticamente y conviene revisarlo.
- Este proyecto depende de extractores de `yt-dlp`; puede necesitar actualizaciones cuando las plataformas cambien su funcionamiento.
- Si YouTube devuelve `HTTP 403`, la aplicacion prueba varios clientes y formatos. Si persiste, puedes probar con cookies del navegador o configurar un proveedor externo de PO Tokens compatible con `yt-dlp`.

## Publicar en GitHub

Inicializa Git, crea el primer commit y conecta tu repositorio remoto:

```bash
git init
git add .
git commit -m "Initial YouTube downloader project"
git branch -M main
git remote add origin <URL_DEL_REPOSITORIO>
git push -u origin main
```

## Crear ejecutable portable para macOS Apple silicon

Desde un Mac Apple silicon, con el entorno virtual creado:

```bash
source venv/bin/activate
./scripts/build_macos_portable.sh
```

El resultado queda en:

```text
dist/YouTubeDownloader-macos-arm64-portable/
```

Esa carpeta es la que puedes copiar al pendrive. Incluye:

```text
YouTubeDownloader
bin/ffmpeg
bin/node
```

El ejecutable portable no incluye Whisper MLX. Para usar esa alternativa, ejecuta la version Python desde el entorno virtual e instala `requirements-whisper-mlx.txt`.

En otro Mac Apple silicon, ejecuta desde Terminal:

```bash
cd /ruta/al/pendrive/YouTubeDownloader-macos-arm64-portable
./YouTubeDownloader --self-test
./YouTubeDownloader
```

Si macOS bloquea el ejecutable por no estar firmado:

```bash
xattr -dr com.apple.quarantine .
./YouTubeDownloader
```
