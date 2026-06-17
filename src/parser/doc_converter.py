import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def _convert_with_soffice(doc_path: Path, out_dir: Path) -> Path:
    for cmd in ("soffice", "libreoffice"):
        exe = shutil.which(cmd)
        if not exe:
            continue
        result = subprocess.run(
            [exe, "--headless", "--convert-to", "docx", "--outdir", str(out_dir), str(doc_path)],
            capture_output=True,
            timeout=120,
        )
        if result.returncode != 0:
            logger.debug("LibreOffice conversion failed: %s", result.stderr.decode(errors="replace"))
            continue
        docx_path = out_dir / f"{doc_path.stem}.docx"
        if docx_path.exists():
            return docx_path
    raise FileNotFoundError("LibreOffice not found")


def _convert_with_powershell_word(doc_path: Path, out_dir: Path) -> Path:
    docx_path = out_dir / f"{doc_path.stem}.docx"
    script = f"""
$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {{
  $doc = $word.Documents.Open('{doc_path.resolve()}')
  $doc.SaveAs2('{docx_path.resolve()}', 16)
  $doc.Close()
}} finally {{
  $word.Quit()
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}}
"""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    if not docx_path.exists():
        raise RuntimeError("Word conversion produced no output")
    return docx_path


def _convert_with_word_com(doc_path: Path, out_dir: Path) -> Path:
    import win32com.client

    docx_path = out_dir / f"{doc_path.stem}.docx"
    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    try:
        doc = word.Documents.Open(str(doc_path.resolve()))
        doc.SaveAs2(str(docx_path.resolve()), FileFormat=16)
        doc.Close()
    finally:
        word.Quit()
    if not docx_path.exists():
        raise RuntimeError("Word conversion produced no output")
    return docx_path


def convert_doc_to_docx(doc_path: str) -> Path:
    path = Path(doc_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {doc_path}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        errors = []
        for converter in (_convert_with_soffice, _convert_with_word_com, _convert_with_powershell_word):
            try:
                docx = converter(path, tmp_dir)
                fd, persistent_name = tempfile.mkstemp(suffix=".docx")
                os.close(fd)
                persistent = Path(persistent_name)
                shutil.copy2(docx, persistent)
                return persistent
            except ImportError:
                errors.append("pywin32 not installed")
            except Exception as exc:
                errors.append(str(exc))
                logger.debug("DOC converter failed (%s): %s", converter.__name__, exc)

    raise RuntimeError(
        "Cannot convert .doc file. Install LibreOffice (recommended) or Microsoft Word with pywin32. "
        f"Errors: {'; '.join(errors)}"
    )
