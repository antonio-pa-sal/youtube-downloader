# YouTube Downloader

Script de terminal en Python para descargar videos de YouTube, seleccionar audio original o doblaje automatico cuando este disponible, fusionar video/audio con `ffmpeg` y generar PDFs de transcripcion.

## Funcionalidades

- Descarga video en 1080p cuando esta disponible.
- Descarga audio original con `pytubefix`.
- Usa `yt-dlp` como respaldo para pistas de doblaje automatico, por ejemplo `es-US`.
- Fusiona video y audio con `ffmpeg`.
- Genera PDFs de transcripcion:
  - con marcas temporales
  - sin marcas temporales, agrupando texto segun puntuacion

## Requisitos

- Python 3.12 recomendado.
- `ffmpeg` instalado y disponible en el `PATH`.
- Node.js instalado y disponible en el `PATH` para resolver algunos formatos de YouTube usados por `yt-dlp`.

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

- URL del video de YouTube.
- Ruta de guardado, con `Downloads` como valor por defecto.
- Idioma deseado para audio/transcripcion, con `es` como valor por defecto.

## Salidas generadas

Segun disponibilidad del video, se generaran archivos como:

```text
<titulo>_1080p_merged.mp4
<titulo>_1080p_es_auto_dub.mp4
<titulo>_transcripcion_original.pdf
<titulo>_transcripcion_original_sin_marcas.pdf
<titulo>_transcripcion_es.pdf
<titulo>_transcripcion_es_sin_marcas.pdf
```

## Notas importantes

- YouTube puede limitar temporalmente la descarga de subtitulos/traducciones con `HTTP Error 429: Too Many Requests`. Si ocurre, espera unos minutos y vuelve a ejecutar.
- No todos los videos ofrecen pista doblada, subtitulos o traduccion automatica.
- Este proyecto depende de APIs no oficiales de YouTube a traves de `pytubefix` y `yt-dlp`; puede necesitar actualizaciones cuando YouTube cambie su funcionamiento.

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
