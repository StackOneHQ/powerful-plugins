"""Optional local OCR; output is evidence to review, never automatic truth."""
import csv
import io
import shutil
import subprocess
import tempfile
from pathlib import Path
from PIL import Image, ImageOps


def read_text(path, *, scale=1., region=None, invert=False, psm=11):
    """Read tokens, retaining their locations in the original image.

    Cropping and rescaling are explicit preprocessing, not new evidence.
    TSV confidence measures recognition, never the truth of a disclosure.
    """
    executable=shutil.which('tesseract')
    if not executable:return {'available':False,'tokens':[],'text':'','reason':'Install Tesseract for local OCR.'}
    with Image.open(path) as original:
        if original.width*original.height>30_000_000:raise ValueError('Image exceeds 30 megapixels')
        if not 0.25<=scale<=4:raise ValueError('OCR scale must be between 0.25 and 4')
        region=region or [0,0,original.width,original.height]
        left,top,right,bottom=map(int,region)
        if not (0<=left<right<=original.width and 0<=top<bottom<=original.height):raise ValueError('OCR region must be inside the image')
        im=original.convert('RGB').crop((left,top,right,bottom))
        target=(round(im.width*scale),round(im.height*scale))
        if target[0]*target[1]>30_000_000:raise ValueError('Rescaled OCR image exceeds 30 megapixels')
        sx,sy=target[0]/im.width,target[1]/im.height
        if target!=im.size:im=im.resize(target,Image.Resampling.LANCZOS)
        if invert:im=ImageOps.invert(im)
        with tempfile.TemporaryDirectory(prefix='chart-ocr-') as tmp:
            prepared=Path(tmp)/'input.png';im.save(prepared)
            try:
                proc=subprocess.run([executable,str(prepared),'stdout','--psm',str(psm),'tsv'],capture_output=True,text=True,encoding="utf-8",timeout=45)
            except subprocess.TimeoutExpired:
                return {'available':False,'tokens':[],'text':'','reason':'OCR timed out'}
    if proc.returncode:return {'available':False,'tokens':[],'text':'','reason':'OCR failed'}
    rows=[]
    for r in csv.DictReader(io.StringIO(proc.stdout),delimiter='\t'):
        text=r.get('text','').strip()
        if text and float(r['conf'])>=30:
            rows.append(dict(text=text,confidence=float(r['conf']),
                             box=[left+int(r['left'])/sx,top+int(r['top'])/sy,int(r['width'])/sx,int(r['height'])/sy],
                             line=[int(r[k]) for k in ('block_num','par_num','line_num')]))
    return {'available':True,'tokens':rows,'text':' '.join(r['text'] for r in rows),
            'preprocessing':{'scale':scale,'region':region,'invert':invert,'psm':psm},
            'warning':'OCR confidence is not calibration confidence; verify units and locations.'}
