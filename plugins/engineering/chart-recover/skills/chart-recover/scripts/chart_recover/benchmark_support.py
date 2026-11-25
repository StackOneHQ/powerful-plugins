"""Environment checks for evaluations that require an external OCR executable."""
import shutil
import subprocess


def require_tesseract():
    if not shutil.which('tesseract'):
        raise ValueError('This evaluation requires Tesseract on PATH; no cases were generated')
    try:
        result=subprocess.run(['tesseract','--version'],capture_output=True,text=True,
                              encoding='utf-8',errors='replace',timeout=10,check=True)
        return result.stdout.splitlines()[0]
    except (OSError,subprocess.SubprocessError,IndexError) as error:
        raise ValueError('Tesseract is unavailable; no evaluation cases were generated') from error
