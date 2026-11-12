"""Inspectable classical-vision baseline. No trained weights or hidden data access."""
from __future__ import annotations
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.signal import find_peaks


def _components(mask):
    labels, n = ndimage.label(mask)
    objects = ndimage.find_objects(labels)
    found = []
    for i, sl in enumerate(objects):
        if sl is None:
            continue
        sy, sx = sl; area = int((labels[sl] == i+1).sum())
        w, h = sx.stop-sx.start, sy.stop-sy.start
        if area >= 15 and max(w, h) >= 5:
            found.append(dict(x=sx.start, y=sy.start, w=w, h=h, area=area, solidity=area/(w*h), label=i+1))
    return labels, found


def _masks(rgb, color=None, *, min_saturation=95):
    if color is not None:
        target = np.array(color, dtype=float)
        yield '#%02x%02x%02x' % tuple(color), np.linalg.norm(rgb.astype(float)-target, axis=2) < 65
        return
    hsv = np.asarray(Image.fromarray(rgb).convert('HSV'))
    quant = rgb.astype(np.int32)//16
    codes = quant[:,:,0]*256 + quant[:,:,1]*16 + quant[:,:,2]
    bg_code = np.bincount(codes.ravel(), minlength=4096).argmax()
    bg = np.median(rgb[codes == bg_code], axis=0)
    foreground = np.linalg.norm(rgb.astype(float)-bg, axis=2) > 38
    eligible = (hsv[:, :, 1] > min_saturation) & (hsv[:, :, 2] > 45) & foreground
    hist = np.bincount((hsv[:, :, 0][eligible].astype(int)*72//256), minlength=72).astype(float)
    smooth = ndimage.gaussian_filter1d(hist, .7, mode='wrap')
    peaks, _ = find_peaks(np.r_[smooth[-1], smooth, smooth[0]], prominence=max(10, smooth.max()*.018))
    peaks = sorted((int(p-1) for p in peaks if 1 <= p <= 72), key=lambda p: smooth[p], reverse=True)
    for peak in peaks[:8]:
        hue = hsv[:, :, 0].astype(float)*72/256
        distance = np.minimum(abs(hue-peak-.5), 72-abs(hue-peak-.5))
        mask = eligible & (distance <= 1.6)
        if mask.sum() < 40:
            continue
        c = tuple(np.median(rgb[mask], axis=0).astype(int))
        yield '#%02x%02x%02x' % c, mask


def extract(path, *, kind='auto', roi=None, color=None, samples=101):
    """roi=[left, top, right, bottom] is optional, in original image pixels.

    Colored 2D bar, horizontal bar, grouped/stacked bar, line, area,
    stacked area and scatter marks. Grayscale needs explicit color.
    Unsupported/uncertain geometry is surfaced, never assigned units.
    """
    supported = {'auto','bar','barh','line','area','scatter','stacked_bar','stacked_area','grouped_bar'}
    if kind not in supported:
        raise ValueError(f'Unsupported chart kind {kind}; supported: {sorted(supported)}')
    im = Image.open(path)
    if im.width*im.height > 30_000_000:
        raise ValueError('Image exceeds 30 megapixels')
    im = im.convert('RGB')
    supplied_roi = roi is not None
    rgb = np.asarray(im)
    if roi is None:
        roi = [0, 0, im.width, im.height]
    left, top, right, bottom = map(int, roi)
    if not (0 <= left < right <= im.width and 0 <= top < bottom <= im.height):
        raise ValueError('ROI must be inside the image')
    rgb = rgb[top:bottom, left:right]
    series, warnings, quality_issues = [], [], []
    for color_hex, mask in _masks(rgb, color):
        labels, comps = _components(mask)
        if not comps:
            continue
        # Text and legend swatches are typically small relative to data marks.
        biggest = max(comps, key=lambda c:c['area'])
        comps = [c for c in comps if c['area'] >= max(15, biggest['area']*.003)]
        actual = kind
        if actual == 'auto':
            rects = [c for c in comps if c['solidity'] > .83 and min(c['w'], c['h']) >= 5]
            if len(rects) >= 2 and len(rects) >= len(comps)*.6:
                by_x=sorted(rects,key=lambda c:c['x']);by_y=sorted(rects,key=lambda c:c['y'])
                vertical=np.ptp([c['y']+c['h']-1 for c in rects])<=max(3,rgb.shape[0]*.006) and all(b['x']>=a['x']+a['w']+1 for a,b in zip(by_x,by_x[1:]))
                horizontal=np.ptp([c['x'] for c in rects])<=max(3,rgb.shape[1]*.006) and all(b['y']>=a['y']+a['h']+1 for a,b in zip(by_y,by_y[1:]))
                if vertical==horizontal:
                    quality_issues.append(dict(reason='Rectangular marks do not establish one shared baseline and bar orientation; specify kind.'))
                    continue
                actual='bar' if vertical else 'barh'
            elif len(rects)==1 and len(comps)==1:
                quality_issues.append(dict(reason='A single rectangular mark does not establish bar orientation or distinguish a bar from a point; specify kind.'))
                continue
            elif biggest['w'] > rgb.shape[1]*.25:
                actual = 'area' if biggest['solidity'] > .2 else 'line'
            else:
                actual = 'scatter'
        points = []; observed_columns = None
        if actual in ('bar','barh','stacked_bar','grouped_bar'):
            horizontal = actual == 'barh'
            for c in comps:
                if c['solidity'] < .70 or min(c['w'], c['h']) < 2:
                    continue
                if horizontal:
                    points.append(dict(x=left+c['x']+c['w']-1, y=top+c['y']+(c['h']-1)/2,
                                       base=left+c['x'], extent=c['w']-1))
                else:
                    points.append(dict(x=left+c['x']+(c['w']-1)/2, y=top+c['y'],
                                       base=top+c['y']+c['h']-1, extent=c['h']-1))
            points.sort(key=lambda p:p['y' if horizontal else 'x'])
        elif actual == 'scatter':
            for c in comps:
                if max(c['w'],c['h'])/min(c['w'],c['h']) > 3 or c['solidity'] < .25:
                    continue
                yy, xx = np.where(labels == c['label'])
                points.append(dict(x=float(xx.mean()+left), y=float(yy.mean()+top)))
            points.sort(key=lambda p:p['x'])
        else:
            # Keep wide components (broken/dashed curves can require explicit ROI).
            keep = [c['label'] for c in comps if c['w'] >= max(5, biggest['w']*.025)]
            clean = np.isin(labels, keep)
            cols = np.where(clean.any(axis=0))[0]
            observed_columns = cols
            if not len(cols):
                continue
            x_samples = np.unique(np.round(np.linspace(cols[0], cols[-1], min(samples, len(cols)))).astype(int))
            for x in x_samples:
                yy = np.where(clean[:, x])[0]
                if not len(yy):
                    continue
                if actual == 'line':
                    y = float(np.median(yy))
                else:
                    neighbors=[np.where(clean[:,cx])[0] for cx in range(max(0,x-2),min(clean.shape[1],x+3))]
                    y=float(np.median([ys.min() for ys in neighbors if len(ys)]))
                p = dict(x=float(x+left), y=y+top)
                if actual in ('area','stacked_area'):
                    p.update(base=float(yy.max()+top), extent=float(yy.max()-yy.min()))
                points.append(p)
        minimum_points = 2 if actual in ('line','area','stacked_area') else 1
        if len(points) >= minimum_points:
            if supplied_roi and actual in ('line','area','stacked_area'):
                coverage=(points[-1]['x']-points[0]['x'])/(right-left)
                if coverage < .70:
                    quality_issues.append(dict(series=f'series_{len(series)}',
                        reason='Trace covers less than 70% of the supplied plot ROI width.',
                        horizontal_coverage=coverage))
                # Span alone cannot distinguish a complete trace from two
                # endpoints separated by a large hidden middle segment. Use
                # observed columns so sparse requested sampling is not a gap.
                gaps=np.diff(observed_columns)-1
                largest_gap=int(gaps.max()) if len(gaps) else 0
                if largest_gap>max(5,(right-left)*.05):
                    quality_issues.append(dict(series=f'series_{len(series)}',
                        reason='Trace contains a large unobserved horizontal gap inside the supplied plot ROI.',
                        largest_unobserved_gap=largest_gap))
            coords = [-p['x'] if actual == 'barh' else p['y'] for p in points]
            q = -np.array(coords); spread = float(np.ptp(q))
            normalized = ((q-q.min())/spread).tolist() if spread else [0.]*len(q)
            series.append(dict(id=f'series_{len(series)}', color=color_hex, kind=actual,
                               points=points, coordinates=coords, shape_normalized=normalized,
                               shape_note='Min-max normalized geometry only; these are not data values or growth ratios.'))
    if kind == 'auto':
        warnings.append('Chart kind inferred heuristically; inspect overlay and specify kind/ROI when necessary.')
    if not series:
        warnings.append('No supported colored series found. Supply plot ROI/color or inspect manually.')
    if len(series) > 1:
        warnings.append('Color separates series; legend names and stack order require confirmation.')
    if quality_issues:
        warnings.append('Incomplete trace in the supplied plot ROI; inspect foreground color and missing segments before calibration.')
    return dict(image=str(Path(path)), size=[im.width, im.height], roi=roi, series=series,
                status='extracted' if series and not quality_issues else 'needs_review', warnings=warnings,quality_issues=quality_issues,
                method='hue segmentation + connected components / column tracing')


def overlay(path, extraction, output):
    im = Image.open(path).convert('RGB'); draw = ImageDraw.Draw(im)
    for series in extraction['series']:
        for p in series['points']:
            x,y=p['x'],p['y']; draw.ellipse([x-2,y-2,x+2,y+2],fill='#ef3054',outline='white')
    im.save(output)
