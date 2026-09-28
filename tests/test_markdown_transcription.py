import contextlib
import importlib.machinery
import io
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import youtube_downloader as downloader


class MarkdownTranscriptTests(unittest.TestCase):
    def test_vtt_caption_parser_returns_text_and_timestamps(self):
        caption_json = downloader.parse_text_caption_file(
            "WEBVTT\n\n00:00:01.200 --> 00:00:02.400\nHola, mundo.\n\n"
            "00:00:03.000 --> 00:00:04.000\nFin.\n"
        )

        self.assertEqual(
            downloader.extract_caption_entries(caption_json),
            [(1_200, "Hola, mundo."), (3_000, "Fin.")],
        )

    def test_markdown_groups_cues_and_preserves_timestamps_and_metadata(self):
        markdown = downloader.build_markdown_transcript(
            "Introducción a NoSQL",
            "Transcripción del audio original (es)",
            "https://vimeo.com/123456?token=private#player",
            "es",
            [
                (0, "NoSQL es *una* base"),
                (1_500, "de datos."),
                (3_000, "Contiene [documentos] y listas."),
            ],
            "Whisper MLX (modelo small)",
            (0, 5),
        )

        self.assertIn("# Introducción a NoSQL — Transcripción del audio original (es)", markdown)
        self.assertIn("**Idioma:** es", markdown)
        self.assertIn("**Origen de la transcripción:** Whisper MLX (modelo small)", markdown)
        self.assertIn("<https://vimeo.com/123456>", markdown)
        self.assertNotIn("private", markdown)
        self.assertIn("**Fragmento:** 00:00:00–00:00:05", markdown)
        self.assertIn("**[00:00:00]** NoSQL es \\*una\\* base de datos.", markdown)
        self.assertIn("**[00:00:03]** Contiene \\[documentos\\] y listas.", markdown)

    def test_markdown_only_writer_creates_utf8_md_without_pdf(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = downloader.write_transcription_outputs(
                temp_dir,
                "Introducción a NoSQL",
                "original",
                "Transcripción del audio original (es)",
                "https://vimeo.com/123456",
                "es",
                [(0, "Adiós, mundo.")],
                "Subtítulos descargados (vtt)",
                "markdown",
            )

            self.assertEqual(len(paths), 1)
            self.assertEqual(Path(paths[0]).name, "Introducción a NoSQL_transcripcion_original.md")
            content = Path(paths[0]).read_text(encoding="utf-8")
            self.assertIn("# Introducción a NoSQL", content)
            self.assertIn("**[00:00:00]** Adiós, mundo.", content)
            self.assertEqual(list(Path(temp_dir).glob("*.pdf")), [])

    def test_both_format_writes_markdown_and_legacy_pdfs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = downloader.write_transcription_outputs(
                temp_dir,
                "Clase",
                "original",
                "Transcripción original",
                "https://vimeo.com/123456",
                "es",
                [(0, "Texto de prueba.")],
                "Whisper MLX",
                "both",
            )

            self.assertEqual(len(paths), 3)
            self.assertTrue((Path(temp_dir) / "Clase_transcripcion_original.md").is_file())
            self.assertEqual(len(list(Path(temp_dir).glob("*.pdf"))), 2)
            for pdf_path in Path(temp_dir).glob("*.pdf"):
                self.assertTrue(pdf_path.read_bytes().startswith(b"%PDF-1.4"))

    def test_menu_accepts_markdown_choice(self):
        output = io.StringIO()
        with patch("builtins.input", side_effect=["invalid", "m"]), contextlib.redirect_stdout(output):
            result = downloader.select_transcription_format()

        self.assertEqual(result, "markdown")
        self.assertIn("Markdown (.md)", output.getvalue())
        self.assertIn("Selección no válida", output.getvalue())

    def test_whisper_fallback_writes_markdown(self):
        class FakeYDL:
            def __init__(self, options):
                self.options = options

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def download(self, _urls):
                audio_path = self.options["outtmpl"].replace("%(ext)s", "wav")
                Path(audio_path).write_bytes(b"fake audio")

        fake_whisper = types.ModuleType("mlx_whisper")
        fake_whisper.transcribe = lambda *_args, **_kwargs: {
            "text": "Transcripción de prueba.",
            "language": "es",
            "segments": [{"start": 0.0, "text": "Transcripción de prueba."}],
        }
        fake_ytdlp = types.ModuleType("yt_dlp")
        fake_ytdlp.YoutubeDL = FakeYDL

        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            downloader.importlib.util,
            "find_spec",
            return_value=importlib.machinery.ModuleSpec("mlx_whisper", loader=None),
        ), patch.object(downloader, "find_executable", return_value=None), patch.dict(
            "sys.modules",
            {"mlx_whisper": fake_whisper, "yt_dlp": fake_ytdlp},
        ):
            completed = downloader.generate_whisper_transcription_pdfs(
                "https://vimeo.com/123456",
                temp_dir,
                "Introducción a NoSQL",
                {1},
                "es",
                transcript_format="markdown",
            )

            output_path = Path(temp_dir) / "Introducción a NoSQL_transcripcion_original.md"
            self.assertEqual(completed, {1})
            self.assertTrue(output_path.exists())
            self.assertIn("Whisper MLX (modelo small)", output_path.read_text(encoding="utf-8"))
            self.assertEqual(list(Path(temp_dir).glob("*.pdf")), [])

    def test_subtitle_path_writes_markdown_without_running_whisper(self):
        class FakeYDL:
            def __init__(self, _options):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def extract_info(self, _url, download=False):
                self.assert_download_false = not download
                return {
                    "language": "es",
                    "automatic_captions": {
                        "es": [{"ext": "json3", "url": "https://captions.invalid/es.json3"}],
                    },
                    "subtitles": {},
                }

        fake_ytdlp = types.ModuleType("yt_dlp")
        fake_ytdlp.YoutubeDL = FakeYDL
        caption_json = {
            "events": [
                {"tStartMs": 0, "segs": [{"utf8": "Texto desde subtítulos."}]},
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            "sys.modules", {"yt_dlp": fake_ytdlp}
        ), patch.object(downloader, "download_caption_json", return_value=caption_json):
            completed = downloader.generate_transcription_pdfs(
                "https://vimeo.com/123456",
                temp_dir,
                "Introducción a NoSQL",
                "es",
                {1},
                transcript_format="markdown",
            )

            output_path = Path(temp_dir) / "Introducción a NoSQL_transcripcion_original.md"
            self.assertEqual(completed, {1})
            self.assertTrue(output_path.exists())
            self.assertIn("Subtítulos descargados (json3)", output_path.read_text(encoding="utf-8"))
            self.assertIn("Texto desde subtítulos.", output_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
