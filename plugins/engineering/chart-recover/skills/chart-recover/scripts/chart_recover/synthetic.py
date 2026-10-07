"""Reproducible synthetic charts; private truth is separate from image inputs."""
from __future__ import annotations
import json
import os
from pathlib import Path
from .render_cache import configure_cache
configure_cache()
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw

KINDS = ('bar','barh','line','area','scatter','grouped_bar','stacked_bar','stacked_area')
PALETTES = [('#4263eb','#e67700','#0ca678'),('#ad45ce','#00a6a6','#ef5b5b'),('#7a5af8','#db8b16','#28ad72')]


def generate_one(folder, seed, kind='bar', scale='linear', variant='clean', renderer='matplotlib'):
    if kind not in KINDS:raise ValueError(f'Unsupported chart kind: {kind}')
    if scale not in ('linear','log'):raise ValueError(f'Unsupported scale: {scale}')
    if variant not in ('clean','truncated','dark','jpeg','small'):raise ValueError(f'Unsupported variant: {variant}')
    if renderer not in ('matplotlib','pillow'):raise ValueError(f'Unsupported renderer: {renderer}')
    if renderer=='pillow' and kind not in ('bar','line','area','scatter'):raise ValueError('Pillow holdout supports bar/line/area/scatter')
    folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    rng=np.random.default_rng(seed); n=int(rng.integers(8,16)); x=np.arange(n)
    values=np.cumsum(rng.uniform(.1,1,n)); values=values/values.max()*10**rng.uniform(2,7)
    if seed%3 == 0:
        values=values*(1+np.sin(np.linspace(0,5,n))*.22)
    nseries=3 if kind in ('grouped_bar','stacked_bar','stacked_area') else 1
    vals=np.array([values*(.5+s*.35)*(1+rng.uniform(-.07,.07,n)) for s in range(nseries)])
    if scale=='log':
        vals=np.array([10**np.linspace(1,3.6,n)*10**rng.uniform(-.05,.05,n) for _ in range(nseries)])
    if variant=='truncated':
        vals+=vals.max()*3
    colors=PALETTES[seed%len(PALETTES)]; dark=variant=='dark'
    width=int(rng.integers(650,1150)); height=int(rng.integers(340,650)); dpi=100
    bg='#111827' if dark else '#ffffff'; fg='#cbd5e1' if dark else '#526074'
    fig,ax=plt.subplots(figsize=(width/dpi,height/dpi),dpi=dpi,facecolor=bg)
    ax.set_facecolor(bg); fig.subplots_adjust(left=.09,right=.97,bottom=.15,top=.85)
    for sp in ax.spines.values(): sp.set_visible(False)
    ax.tick_params(colors=fg,labelsize=9,length=0)
    ax.set_title('Growth over time',loc='left',color=fg,fontsize=15,pad=18)
    maxv=float(vals.sum(axis=0).max()) if kind.startswith('stacked') else float(vals.max())
    low=float(vals.min()*.85) if scale=='log' or variant=='truncated' else 0.
    high=maxv*(1.25 if scale=='log' else 1.12)
    if kind=='barh':
        if scale=='log':ax.set_xscale('log')
        ax.barh(x,vals[0],color=colors[0],height=.65); ax.set_xlim(low,high)
        ax.set_xticks(np.linspace(low,high,6));ax.set_xticklabels([]);ax.set_yticks(x, [f'M{i+1}' for i in x])
        ax.xaxis.grid(True,color=fg,alpha=.12); ax.set_axisbelow(True)
    else:
        if scale=='log':ax.set_yscale('log')
        ax.set_ylim(low,high)
        if kind=='bar':ax.bar(x,vals[0],color=colors[0],width=.65)
        elif kind=='line':ax.plot(x,vals[0],color=colors[0],lw=2.8)
        elif kind=='area':ax.fill_between(x,vals[0],low,color=colors[0],alpha=.85)
        elif kind=='scatter':ax.scatter(x,vals[0],color=colors[0],s=45)
        elif kind=='grouped_bar':
            for j in range(nseries):ax.bar(x+(j-1)*.24,vals[j],width=.21,color=colors[j])
        elif kind=='stacked_bar':
            b=np.zeros(n)
            for j in range(nseries):ax.bar(x,vals[j],bottom=b,width=.65,color=colors[j]);b+=vals[j]
        elif kind=='stacked_area':ax.stackplot(x,*vals,colors=colors)
        ticks=np.geomspace(low,high,6) if scale=='log' else np.linspace(low,high,6)
        ax.set_yticks(ticks);ax.set_yticklabels([]);ax.tick_params(axis='y',which='both',left=False,labelleft=False)
        ax.set_xticks(x[::max(1,n//8)],[f'M{i+1}' for i in x[::max(1,n//8)]])
        ax.yaxis.grid(True,color=fg,alpha=.12);ax.set_axisbelow(True)
    ax.yaxis.get_offset_text().set_visible(False);ax.xaxis.get_offset_text().set_visible(False)
    fig.canvas.draw()
    truth_series=[]; cumulative=np.zeros(n)
    for j,v in enumerate(vals):
        yy=v+cumulative if kind.startswith('stacked') else v
        xx=x+(j-1)*.24 if kind=='grouped_bar' else x
        coords=ax.transData.transform(np.c_[v,x] if kind=='barh' else np.c_[xx,yy])
        points=[{'x':float(p[0]),'y':float(height-p[1]),'value':float(value)} for p,value in zip(coords,yy)]
        truth_series.append({'color':colors[j],'points':points,'segment_values':v.tolist()})
        cumulative+=v
    baseline=ax.transData.transform((0,0) if scale!='log' else (low,0) if kind=='barh' else (0,low))
    path=folder/'chart.png';fig.savefig(path,facecolor=bg,dpi=dpi);plt.close(fig)
    if renderer=='pillow':
        # Independent rasterizer using the same declared data-to-pixel transform.
        im=Image.new('RGB',(width,height),bg);d=ImageDraw.Draw(im)
        d.text((width*.09,18),'Growth over time',fill=fg)
        for j,s in enumerate(truth_series):
            pts=[(p['x'],p['y']) for p in s['points']]
            if kind=='bar':
                bw=(pts[1][0]-pts[0][0])*.62
                for px,py in pts:d.rectangle((px-bw/2,py,px+bw/2,height-baseline[1]),fill=colors[j])
            elif kind=='line':d.line(pts,fill=colors[j],width=3)
            elif kind=='area':d.polygon([(pts[0][0],height-baseline[1])]+pts+[(pts[-1][0],height-baseline[1])],fill=colors[j])
            elif kind=='scatter':
                for px,py in pts:d.ellipse((px-4,py-4,px+4,py+4),fill=colors[j])
            else:raise ValueError('Pillow holdout supports bar/line/area/scatter')
        im.save(path)
    if variant=='jpeg':
        im=Image.open(path).convert('RGB'); im.save(folder/'compressed.jpg',quality=48);Image.open(folder/'compressed.jpg').save(path)
    if variant=='small':
        # Downsampling exercises antialiasing without silently changing truth coordinates.
        im=Image.open(path);im.resize((width//2,height//2),Image.Resampling.BILINEAR).resize((width,height),Image.Resampling.BILINEAR).save(path)
    truth=dict(seed=seed,kind=kind,scale=scale,variant=variant,renderer=renderer,series=truth_series,
               size=[width,height],axis_limits=[low,high],baseline_pixel=float(-baseline[0] if kind=='barh' else height-baseline[1]))
    (folder/'truth.json').write_text(json.dumps(truth,indent=2), encoding="utf-8")
    return truth


def collision_demo(folder):
    """Different absolute numbers produce byte-identical hidden-axis PNGs."""
    import hashlib
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    records=[]
    for mult in (1,1000):
        values=np.array([10,15,22,31,49,80])*mult
        im=Image.new('RGB',(640,360),'white');d=ImageDraw.Draw(im)
        for i,v in enumerate(values):
            x=50+i*90;top=320-round(v/(100*mult)*260)
            d.rectangle((x,top,x+55,320),fill='#4263eb')
        path=folder/f'scale_{mult}.png';im.save(path)
        records.append(dict(file=path.name,values=values.tolist(),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    result=dict(identical_images=records[0]['sha256']==records[1]['sha256'],examples=records,
                implication='No image-only model can uniquely distinguish these scales. More training cannot supply missing information.')
    (folder/'proof.json').write_text(json.dumps(result,indent=2), encoding="utf-8");return result
