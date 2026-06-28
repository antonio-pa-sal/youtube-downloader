from pytubefix import YouTube
from pytubefix.exceptions import VideoUnavailable, RegexMatchError
import html
import json
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import re
import urllib.request

SPANISH_AUDIO_NAMES = {"spanish", "español", "espanol", "castellano", "latino"}
PDF_PAGE_WIDTH = 595
PDF_PAGE_HEIGHT = 842
PDF_MARGIN = 50
PDF_FONT_SIZE = 10
PDF_LINE_HEIGHT = 14

def application_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def bundled_bin_dir() -> str:
    return os.path.join(application_dir(), "bin")

def find_executable(name: str) -> str | None:
    extension = ".exe" if os.name == "nt" else ""
    bundled_executable = os.path.join(bundled_bin_dir(), f"{name}{extension}")
    if os.path.exists(bundled_executable):
        return bundled_executable
    return shutil.which(name)

def setup_portable_environment() -> None:
    bin_dir = bundled_bin_dir()
    if os.path.isdir(bin_dir):
        os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"

    try:
        import certifi
        os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    except ImportError:
        pass

def run_ytdlp(args: list[str], env: dict | None = None) -> int:
    if getattr(sys, "frozen", False):
        import yt_dlp
        old_argv = sys.argv[:]
        try:
            sys.argv = ["yt-dlp", *args]
            try:
                yt_dlp.main(args)
            except SystemExit as e:
                return int(e.code or 0) if isinstance(e.code, int) else 1
            return 0
        finally:
            sys.argv = old_argv

    cmd = [sys.executable, "-m", "yt_dlp", *args]
    result = subprocess.run(cmd, env=env)
    return result.returncode

def run_self_test() -> int:
    setup_portable_environment()
    print("YouTubeDownloader self-test")
    print(f"Application dir: {application_dir()}")

    ffmpeg_path = find_executable("ffmpeg")
    node_path = find_executable("node")
    print(f"ffmpeg: {ffmpeg_path or 'not found'}")
    print(f"node: {node_path or 'not found'}")

    if not ffmpeg_path or not node_path:
        return 1

    ffmpeg_result = subprocess.run(
        [ffmpeg_path, "-version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    node_result = subprocess.run(
        [node_path, "--version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    print(ffmpeg_result.stdout.splitlines()[0] if ffmpeg_result.stdout else "ffmpeg version unavailable")
    print(f"node {node_result.stdout.strip()}")

    try:
        import certifi
        import pytubefix
        import yt_dlp
        print(f"certifi: {certifi.where()}")
        print(f"pytubefix: {getattr(pytubefix, '__version__', 'installed')}")
        print(f"yt-dlp: {yt_dlp.version.__version__}")
    except Exception as e:
        print(f"Dependency import failed: {e}")
        return 1

    print("Self-test OK")
    return 0

def sanitize_filename(name: str) -> str:
    """
    Limpia el título para usarlo como nombre de archivo.
    Elimina caracteres problemáticos para el sistema de archivos.
    """
    name = re.sub(r'[\\/*?:"<>|]', "_", name)
    name = name.strip()
    if not name:
        name = "video_descargado"
    return name

def pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

def wrap_text(text: str, max_chars: int = 92) -> list[str]:
    words = text.split()
    lines = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current = f"{current} {word}".strip()
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]

def write_simple_pdf(path: str, title: str, lines: list[str]) -> None:
    pages = []
    y_start = PDF_PAGE_HEIGHT - PDF_MARGIN
    y_bottom = PDF_MARGIN
    current_page = []
    y = y_start

    for line in lines:
        for wrapped_line in wrap_text(line):
            if y < y_bottom:
                pages.append(current_page)
                current_page = []
                y = y_start
            current_page.append((PDF_MARGIN, y, wrapped_line))
            y -= PDF_LINE_HEIGHT

    if current_page:
        pages.append(current_page)

    objects = []
    objects.append("<< /Type /Catalog /Pages 2 0 R >>")
    page_ids = []
    content_ids = []
    first_page_obj = 3
    for index in range(len(pages)):
        page_ids.append(first_page_obj + index * 2)
        content_ids.append(first_page_obj + index * 2 + 1)

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>")

    for page_id, content_id, page_lines in zip(page_ids, content_ids, pages):
        stream_lines = ["BT", f"/F1 {PDF_FONT_SIZE} Tf", f"{PDF_LINE_HEIGHT} TL"]
        for x, y_pos, text in page_lines:
            safe_text = pdf_escape(text).encode("cp1252", "replace").decode("cp1252")
            stream_lines.append(f"1 0 0 1 {x} {y_pos} Tm ({safe_text}) Tj")
        stream_lines.append("ET")
        stream = "\n".join(stream_lines)

        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PDF_PAGE_WIDTH} {PDF_PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >> >> >> "
            f"/Contents {content_id} 0 R >>"
        )
        objects.append(f"<< /Length {len(stream.encode('cp1252', 'replace'))} >>\nstream\n{stream}\nendstream")

    pdf = ["%PDF-1.4\n"]
    offsets = [0]
    for object_number, body in enumerate(objects, start=1):
        offsets.append(sum(len(part.encode("cp1252", "replace")) for part in pdf))
        pdf.append(f"{object_number} 0 obj\n{body}\nendobj\n")

    xref_offset = sum(len(part.encode("cp1252", "replace")) for part in pdf)
    pdf.append(f"xref\n0 {len(objects) + 1}\n")
    pdf.append("0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.append(f"{offset:010d} 00000 n \n")
    pdf.append(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Title ({pdf_escape(title)}) >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    )

    with open(path, "wb") as pdf_file:
        pdf_file.write("".join(pdf).encode("cp1252", "replace"))

def format_timestamp(milliseconds: int) -> str:
    total_seconds = milliseconds // 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def extract_caption_entries(caption_json: dict) -> list[tuple[int, str]]:
    entries = []
    previous_text = None
    for event in caption_json.get("events", []):
        segments = event.get("segs") or []
        text = "".join(segment.get("utf8", "") for segment in segments)
        text = html.unescape(re.sub(r"\s+", " ", text)).strip()
        if not text or text == previous_text:
            continue
        entries.append((int(event.get("tStartMs", 0)), text))
        previous_text = text
    return entries

def captions_to_lines(caption_json: dict, heading: str) -> list[str]:
    lines = [heading, ""]
    for start_ms, text in extract_caption_entries(caption_json):
        timestamp = format_timestamp(start_ms)
        lines.append(f"[{timestamp}] {text}")
    return lines

def caption_entries_to_clean_lines(entries: list[tuple[int, str]], heading: str) -> list[str]:
    lines = [heading, ""]
    paragraph_parts = []

    for _, text in entries:
        paragraph_parts.append(text)
        current_text = " ".join(paragraph_parts).strip()
        if re.search(r'[.!?;:。！？]["”’)]?$', current_text):
            lines.extend(wrap_text(current_text, max_chars=92))
            lines.append("")
            paragraph_parts = []

    if paragraph_parts:
        lines.extend(wrap_text(" ".join(paragraph_parts).strip(), max_chars=92))

    return lines

def find_caption_track(captions: dict, preferred_codes: list[str]):
    for code in preferred_codes:
        tracks = captions.get(code) or []
        json_tracks = [track for track in tracks if track.get("ext") == "json3"]
        if json_tracks:
            return code, json_tracks[0]
    return None, None

def download_caption_json(track: dict) -> dict:
    request = urllib.request.Request(
        track["url"],
        headers={"User-Agent": "Mozilla/5.0"}
    )
    context = None
    try:
        import certifi
        context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass

    with urllib.request.urlopen(request, timeout=30, context=context) as response:
        return json.loads(response.read().decode("utf-8"))

def download_caption_json_with_ytdlp(url: str, language_code: str) -> dict:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_template = os.path.join(temp_dir, "%(id)s.%(ext)s")
        args = [
            "--skip-download",
            "--write-auto-subs",
            "--sub-langs", language_code,
            "--sub-format", "json3",
            "--sleep-subtitles", "5",
            "-o", output_template,
            url,
        ]
        node_path = find_executable("node")
        if node_path:
            args[0:0] = [
                "--js-runtimes", f"node:{node_path}",
                "--remote-components", "ejs:github",
                "--impersonate", "chrome",
            ]
        env = os.environ.copy()
        try:
            import certifi
            env.setdefault("SSL_CERT_FILE", certifi.where())
        except ImportError:
            pass

        returncode = run_ytdlp(args, env=env)
        if returncode != 0:
            raise RuntimeError(f"yt-dlp terminó con código {returncode}")

        for filename in os.listdir(temp_dir):
            if filename.endswith(f".{language_code}.json3"):
                with open(os.path.join(temp_dir, filename), "r", encoding="utf-8") as caption_file:
                    return json.load(caption_file)

    raise FileNotFoundError(f"No se generó el subtítulo {language_code} con yt-dlp.")

def generate_transcription_pdfs(url: str, download_path: str, title: str, language_code: str) -> None:
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        print("⚠️  yt-dlp no está instalado; no se generarán transcripciones PDF.")
        return

    print("\nGenerando transcripciones PDF desde los subtítulos de YouTube...")
    safe_title = sanitize_filename(title)
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "no_warnings": True,
        "extractor_args": {"youtube": {"player_client": ["android_vr", "web"]}},
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        print(f"⚠️  No se pudieron obtener subtítulos para transcripción: {e}")
        return

    captions = info.get("automatic_captions") or {}
    if not captions:
        print("⚠️  YouTube no devolvió subtítulos automáticos para generar PDF.")
        return

    transcript_requests = [
        ("original", "Transcripción del audio original", ["en-orig", "en-US", "en"]),
        (language_code, f"Transcripción/traducción en {language_code}", [language_code, f"{language_code}-US", "es", "es-US"]),
    ]

    created_files = []
    for suffix, heading, codes in transcript_requests:
        code, track = find_caption_track(captions, codes)
        if not track:
            print(f"⚠️  No se encontró transcripción para: {heading}")
            continue

        try:
            if suffix == "original":
                caption_json = download_caption_json(track)
            else:
                caption_json = download_caption_json_with_ytdlp(url, code)
        except Exception as first_error:
            try:
                if suffix == "original":
                    caption_json = download_caption_json_with_ytdlp(url, code)
                else:
                    caption_json = download_caption_json(track)
            except Exception as second_error:
                print(f"⚠️  No se pudo descargar la transcripción {code}: {first_error}; respaldo: {second_error}")
                continue

        caption_entries = extract_caption_entries(caption_json)
        lines = captions_to_lines(caption_json, f"{heading} ({code})")
        clean_lines = caption_entries_to_clean_lines(
            caption_entries,
            f"{heading} sin marcas temporales ({code})"
        )
        if len(lines) <= 2:
            print(f"⚠️  La transcripción {code} está vacía.")
            continue

        output_file = os.path.join(download_path, f"{safe_title}_transcripcion_{suffix}.pdf")
        write_simple_pdf(output_file, f"{title} - {heading}", lines)
        created_files.append(output_file)

        clean_output_file = os.path.join(download_path, f"{safe_title}_transcripcion_{suffix}_sin_marcas.pdf")
        write_simple_pdf(clean_output_file, f"{title} - {heading} sin marcas temporales", clean_lines)
        created_files.append(clean_output_file)

    for file_path in created_files:
        print(f"✅ PDF generado: {file_path}")

def abr_to_int(abr: str | None) -> int:
    """Convierte valores tipo '128kbps' en enteros para comparar calidad."""
    if not abr:
        return 0
    match = re.search(r"\d+", abr)
    return int(match.group()) if match else 0

def describe_audio_track(stream) -> str:
    name = stream.audio_track_name_regionalized or stream.audio_track_name or "original"
    language = stream.audio_track_language_id_regionalized or stream.audio_track_language_id or "desconocido"
    return f"{name} ({language}, {stream.abr})"

def is_requested_audio_track(stream, language_code: str) -> bool:
    language_code = language_code.lower()
    track_name = (stream.audio_track_name or "").lower()
    regionalized_name = (stream.audio_track_name_regionalized or "").lower()
    language_id = (stream.audio_track_language_id or "").lower()
    regionalized_language_id = (stream.audio_track_language_id_regionalized or "").lower()

    if language_id == language_code or regionalized_language_id == language_code:
        return True

    if language_code == "es":
        return (
            track_name in SPANISH_AUDIO_NAMES
            or regionalized_name in SPANISH_AUDIO_NAMES
            or regionalized_language_id.startswith("es-")
        )

    return False

def select_audio_stream(streams, language_code: str = "es"):
    audio_streams = list(streams.filter(only_audio=True))
    requested_streams = [
        stream for stream in audio_streams
        if is_requested_audio_track(stream, language_code)
    ]

    if requested_streams:
        return max(requested_streams, key=lambda stream: abr_to_int(stream.abr)), True, audio_streams

    default_audio_streams = list(streams.get_default_audio_track().filter(only_audio=True))
    fallback_streams = default_audio_streams or audio_streams
    if not fallback_streams:
        return None, False, audio_streams

    return max(fallback_streams, key=lambda stream: abr_to_int(stream.abr)), False, audio_streams

def download_auto_dub_with_ytdlp(url: str, download_path: str, title: str, language_code: str) -> bool:
    """Descarga pistas de doblaje automático que no aparecen en pytubefix."""
    node_path = find_executable("node")
    if not node_path:
        print("⚠️  No se encontró Node.js, necesario para resolver algunas pistas de YouTube con yt-dlp.")
        return False

    safe_title = sanitize_filename(title)
    output_template = os.path.join(
        download_path,
        f"{safe_title}_1080p_{language_code}_auto_dub.%(ext)s"
    )
    format_selector = (
        f"best[language^={language_code}][height<=1080]/"
        f"best[language={language_code}][height<=1080]/"
        f"best[language^={language_code}]"
    )

    print("\nProbando descarga con yt-dlp para pistas de doblaje automático...")
    base_args = [
        "--js-runtimes", f"node:{node_path}",
        "--remote-components", "ejs:github",
        "--merge-output-format", "mp4",
        "-f", format_selector,
        "-o", output_template,
        url,
    ]
    commands = [
        base_args,
        base_args[:4] + ["--impersonate", "chrome"] + base_args[4:],
    ]

    env = os.environ.copy()
    try:
        import certifi
        env.setdefault("SSL_CERT_FILE", certifi.where())
    except ImportError:
        pass

    for index, args in enumerate(commands, start=1):
        returncode = run_ytdlp(args, env=env)
        if returncode == 0:
            print("✅ Descarga con doblaje automático completada.")
            print(f"📁 Archivo guardado en: {download_path}")
            return True

        if index < len(commands):
            print("⚠️  Primer intento con yt-dlp falló; probando modo alternativo...")

    print("❌ yt-dlp no pudo descargar una pista de doblaje automático para ese idioma.")
    return False

def download_youtube_video_separated():
    """
    Descarga por separado el track de video (1080p) y el track de audio
    usando pytubefix, y luego los fusiona en un único archivo MP4 con ffmpeg.
    """

    print("--- Descargador Separado (1080p Video + Audio) ---")

    # --- 1. Entrada de la URL ---
    while True:
        url = input("Por favor, introduce la URL del video de YouTube: ").strip()
        if url:
            break
        print("La URL no puede estar vacía.")

    # --- 2. Ruta de Guardado ---
    default_path = os.path.join(os.path.expanduser('~'), 'Downloads')
    if not os.path.isdir(default_path):
        default_path = os.getcwd()

    print(f"\nRuta por defecto: {default_path}")
    download_path = input("Ruta de guardado (Intro para usar por defecto): ").strip() or default_path
    audio_language = input("Idioma de audio deseado (Intro para español/es): ").strip().lower() or "es"

    try:
        if not os.path.exists(download_path):
            os.makedirs(download_path)
    except OSError as e:
        print(f"Error al crear directorio: {e}")
        return

    # --- 3. Proceso de Descarga ---
    try:
        print("\nConectando con YouTube...")
        yt = YouTube(url)
        print(f"Título: **{yt.title}**")
        generate_transcription_pdfs(url, download_path, yt.title, audio_language)

        # A. BUSCAR VIDEO 1080p (Solo video, sin audio)
        print("Buscando stream de video 1080p...")
        video_stream = yt.streams.filter(res="1080p", adaptive=True, file_extension="mp4").first()

        if not video_stream:
            print("⚠️  No se encontró una versión en 1080p para este video.")
            print("Intentando buscar la mayor resolución disponible...")
            video_stream = (
                yt.streams
                .filter(adaptive=True, file_extension="mp4")
                .order_by("resolution")
                .desc()
                .first()
            )
            if video_stream:
                print(f"Se descargará en: {video_stream.resolution}")
            else:
                print("❌ No se encontró ningún stream de video válido.")
                return

        # B. BUSCAR AUDIO (Idioma deseado, si YouTube lo ofrece)
        print(f"Buscando stream de audio en idioma: {audio_language}...")
        audio_stream, requested_audio_found, available_audio_streams = select_audio_stream(
            yt.streams,
            audio_language
        )

        if available_audio_streams:
            print("\nPistas de audio detectadas:")
            seen_tracks = set()
            for stream in available_audio_streams:
                track_description = describe_audio_track(stream)
                if track_description not in seen_tracks:
                    print(f"  - {track_description}")
                    seen_tracks.add(track_description)

        if audio_stream and requested_audio_found:
            print(f"Audio seleccionado: {describe_audio_track(audio_stream)}")
        elif audio_stream:
            print(f"⚠️  No se encontró audio en '{audio_language}'.")
            if download_auto_dub_with_ytdlp(url, download_path, yt.title, audio_language):
                print("\n✨ ¡Proceso finalizado!")
                return
            print(f"Se usará: {describe_audio_track(audio_stream)}")

        # --- 4. Descargar Archivos ---

        # Descarga del VIDEO
        print(f"\n⬇️  Descargando VIDEO ({video_stream.resolution})...")
        video_file = video_stream.download(
            output_path=download_path,
            filename_prefix="VIDEO_Only_"
        )
        print(f"✅ Video guardado: {os.path.basename(video_file)}")

        # Descarga del AUDIO
        audio_file = None
        if audio_stream:
            print(f"\n⬇️  Descargando AUDIO ({describe_audio_track(audio_stream)})...")
            audio_file = audio_stream.download(
                output_path=download_path,
                filename_prefix="AUDIO_Only_"
            )
            print(f"✅ Audio guardado: {os.path.basename(audio_file)}")
        else:
            print("⚠️  No se encontró stream de audio separado.")
            print("No se puede realizar la fusión sin un track de audio.")
            return

        # --- 5. Fusión con ffmpeg ---
        print("\n🎬 Fusionando VIDEO + AUDIO en un único archivo MP4...")

        safe_title = sanitize_filename(yt.title)
        output_file = os.path.join(download_path, f"{safe_title}_1080p_merged.mp4")
        ffmpeg_path = find_executable("ffmpeg")
        if not ffmpeg_path:
            print("❌ No se encontró el ejecutable 'ffmpeg'.")
            print("Incluye ffmpeg en la carpeta 'bin' junto al ejecutable o instálalo en el PATH.")
            print("ℹ️ Los archivos de solo vídeo y audio se mantienen.")
            return

        cmd = [
            ffmpeg_path,
            "-y",
            "-i", video_file,
            "-i", audio_file,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            output_file
        ]

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if result.returncode == 0:
                print(f"✅ Fusión completada correctamente.")
                print(f"📁 Archivo final: {output_file}")

                # --- 6. Borrar archivos temporales (video y audio separados) ---
                try:
                    if os.path.exists(video_file):
                        os.remove(video_file)
                    if os.path.exists(audio_file):
                        os.remove(audio_file)
                    print("🧹 Archivos temporales (VIDEO_Only_*, AUDIO_Only_*) eliminados.")
                except OSError as e:
                    print(f"⚠️ No se pudieron eliminar los archivos temporales: {e}")

            else:
                print("❌ Error al fusionar con ffmpeg.")
                print("Salida de ffmpeg (stderr):")
                print(result.stderr)
                print("ℹ️ Los archivos de solo vídeo y audio se mantienen para revisar el problema.")

        except FileNotFoundError:
            print("❌ No se encontró el ejecutable 'ffmpeg'.")
            print("Asegúrate de tener ffmpeg instalado y accesible en el PATH del sistema.")
            print("Por ejemplo, en macOS puedes instalarlo con: brew install ffmpeg")
            print("ℹ️ Los archivos de solo vídeo y audio se mantienen.")

        print("\n✨ ¡Proceso finalizado!")
        print(f"Archivos en: {download_path}")

    except VideoUnavailable:
        print("❌ Error: Video no disponible.")
    except RegexMatchError:
        print("❌ Error: URL inválida.")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        raise SystemExit(run_self_test())
    setup_portable_environment()
    download_youtube_video_separated()
