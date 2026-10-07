"""Conservative layout proposals for isolated vertical bar cards.

No axes, numeric values, chart kind or ROI are supplied to this detector.
It groups solid, contrasting rectangles by width and common baseline.
Multiple plausible layouts remain candidates; they are not silently ranked.
"""
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage
from .vision import _components


def _same_rectangle(a,b):
    if max(abs(a[i]-b[i]) for i in range(4))<3:return True
    overlap=max(0,min(a[0]+a[2],b[0]+b[2])-max(a[0],b[0]))*max(0,min(a[1]+a[3],b[1]+b[3])-max(a[1],b[1]))
    union=a[2]*a[3]+b[2]*b[3]-overlap
    return overlap/union>.85


def detect_bars(path):
    with Image.open(path) as im:
        if im.width*im.height>30_000_000:raise ValueError('Image exceeds 30 megapixels')
        size=list(im.size)
        ratio=min(1.,1400/max(im.size))
        rgb=np.asarray(im.convert('RGB').resize((round(im.width*ratio),round(im.height*ratio))))
    # Suppress JPEG speckles before proposing fill colors. A color tolerance
    # joins nearby compression shades without requiring exact palette bins.
    rgb=ndimage.median_filter(rgb,size=(3,3,1))
    h,w=rgb.shape[:2]
    q=rgb.astype(np.int32)//16;codes=q[:,:,0]*256+q[:,:,1]*16+q[:,:,2]
    counts=np.bincount(codes.ravel(),minlength=4096)
    regions=[];seen_colors=[]
    for code in np.argsort(counts)[-96:][::-1]:
        if counts[code]<max(80,w*h*.0003):continue
        color=np.median(rgb[codes==code],axis=0)
        if any(np.linalg.norm(color-prior)<22 for prior in seen_colors):continue
        seen_colors.append(color)
        mask=np.linalg.norm(rgb.astype(float)-color,axis=2)<26
        # Close compression pinholes, but do not join separate bars.
        mask=ndimage.binary_closing(mask,structure=np.ones((3,3)))
        labels,components=_components(mask)
        for c in components:
            x,y,bw,bh=c['x'],c['y'],c['w'],c['h']
            if not (max(6,w*.01)<=bw<w*.35 and 2<=bh<h*.80 and c['solidity']>.86):continue
            if bw*bh>w*h*.30:continue
            # Flat rectangles against a contrasting local backdrop; gradient
            # quantization patches usually fail this side-contrast check.
            fill=np.median(rgb[y:y+bh,x:x+bw][labels[y:y+bh,x:x+bw]==c['label']],axis=0)
            pad=max(3,round(bw*.08));a=max(0,x-pad);b=min(w,x+bw+pad)
            side=np.concatenate([rgb[y+bh//4:y+3*bh//4,a:x].reshape(-1,3),rgb[y+bh//4:y+3*bh//4,x+bw:b].reshape(-1,3)])
            if not len(side) or np.linalg.norm(fill-np.median(side,axis=0))<28:continue
            box=[x,y,bw,bh]
            # JPEG edge shades can yield overlapping masks of the same bar.
            if any(_same_rectangle(box,r['box']) for r in regions):continue
            regions.append(dict(box=box,color=fill.astype(int).tolist(),solidity=c['solidity']))
    groups=[]
    for seed in regions:
        x,y,bw,bh=seed['box'];base=y+bh-1
        group=[r for r in regions if abs(r['box'][1]+r['box'][3]-1-base)<=max(3,h*.006)
               and .72<=r['box'][2]/bw<=1.38]
        group.sort(key=lambda r:r['box'][0])
        if len(group)<3:continue
        if any(b['box'][0] < a['box'][0]+a['box'][2]+2 for a,b in zip(group,group[1:])):continue
        centers=[r['box'][0]+r['box'][2]/2 for r in group]
        gaps=np.diff(centers)
        if max(gaps)/min(gaps)>1.45:continue
        if np.ptp([r['box'][1] for r in group])<8:continue
        key=tuple(tuple(r['box']) for r in group)
        if any(g['_key']==key for g in groups):continue
        points=[dict(x=(r['box'][0]+(r['box'][2]-1)/2)/ratio,y=r['box'][1]/ratio,
                     base=(r['box'][1]+r['box'][3]-1)/ratio,extent=(r['box'][3]-1)/ratio,
                     width=r['box'][2]/ratio,color=r['color']) for r in group]
        coords=[p['y'] for p in points];q=-np.array(coords)
        groups.append(dict(_key=key,id=f'candidate_{len(groups)}',kind='bar',points=points,coordinates=coords,
                           color='mixed',shape_normalized=((q-q.min())/np.ptp(q)).tolist(),
                           shape_note='Geometry only; common baseline is not evidence of zero.',
                           roi=[min(p['x']-p['width']/2 for p in points),min(coords),
                                max(p['x']+p['width']/2 for p in points),max(p['base'] for p in points)]))
    for g in groups:g.pop('_key')
    return dict(image=str(Path(path)),size=size,candidates=groups,rectangle_count=len(regions),
                method='solid local-contrast rectangles grouped by width, spacing and baseline',
                status='unique_candidate' if len(groups)==1 else 'needs_review')
