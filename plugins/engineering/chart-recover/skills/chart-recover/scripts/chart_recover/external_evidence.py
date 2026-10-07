"""Test a dated public revenue table against one automatically traced curve.

The source link and numerical agreement support a conditional association;
they cannot establish that the image belongs to that business or reporting year.
"""
from datetime import date
from pathlib import Path
import csv
import hashlib
import json
import re
import numpy as np
from PIL import Image
from scipy import ndimage
from .vision import _masks, overlay
from .ocr import read_text
from .autopilot import consensus_tokens, _center
from .calendar_vision import MONTHS
from .calibrate import calibrate


def seeded_curve_masks(rgb, *, min_saturation=95, hue_tolerance=2):
    """Strong hue seeds admit faint observed pixels; never generate a bridge.

    JPEG and antialiasing can lower saturation while preserving hue. Hue peaks
    still come from the original conservative detector. Expansion uses the same
    foreground-distance test and a fixed lower saturation threshold.
    """
    hsv=np.asarray(Image.fromarray(rgb).convert('HSV'))
    quant=rgb.astype(np.int32)//16;codes=quant[:,:,0]*256+quant[:,:,1]*16+quant[:,:,2]
    bg_code=np.bincount(codes.ravel(),minlength=4096).argmax()
    bg=np.median(rgb[codes==bg_code],axis=0)
    foreground=(hsv[:,:,2]>45)&(np.linalg.norm(rgb.astype(float)-bg,axis=2)>38)
    eligible=(hsv[:,:,1]>55)&foreground
    hue=hsv[:,:,0].astype(float)
    for color,strong in _masks(rgb,min_saturation=min_saturation):
        angles=hue[strong]*2*np.pi/256
        center=(np.arctan2(np.sin(angles).mean(),np.cos(angles).mean())*256/(2*np.pi))%256
        distance=np.minimum(abs(hue-center),256-abs(hue-center))
        same_hue=distance<=256*hue_tolerance/72
        weak=strong|(eligible&same_hue)
        # A translucent area fill can fall below the tracing threshold while
        # its antialiased bottom border exceeds it. These pixels only classify
        # gaps between bands; they never become curve coordinates.
        fill_support=(hsv[:,:,1]>25)&foreground&same_hue
        yield color,strong,weak,fill_support


def trace_curve(image, *, min_saturation=95, hue_tolerance=2, group_radius=1, max_column_gap=5):
    with Image.open(image) as original:
        if original.width * original.height > 30_000_000:
            raise ValueError('Image exceeds 30 megapixels')
        im = original.convert('RGB')
    rgb = np.asarray(im)
    candidates = [];rejections=[]
    for color, strong, original, fill_support in seeded_curve_masks(rgb,min_saturation=min_saturation,hue_tolerance=hue_tolerance):
        # Join raster diagonals and tiny antialiasing gaps, then trace original
        # pixels only. Dilation is used for grouping, never as observed geometry.
        grouped = ndimage.binary_dilation(original, structure=np.ones((2*group_radius+1, 2*group_radius+1)))
        labels, _ = ndimage.label(grouped, structure=np.ones((3, 3)))
        for label, slices in enumerate(ndimage.find_objects(labels), 1):
            if slices is None:
                continue
            sy, sx = slices
            w, h = sx.stop - sx.start, sy.stop - sy.start
            if w < max(180, im.width * .4) or h < 8 or w / h < 1.25:
                continue
            if sx.start < 3 or sy.start < 3 or sx.stop > im.width - 3 or sy.stop > im.height - 3:
                continue
            local = (labels[slices] == label)
            if local.mean() > .9:
                continue
            region = ndimage.binary_dilation(local, structure=np.ones((3, 3)))
            pixels = original[slices] & region
            core = strong[slices] & region
            xs = np.where(pixels.any(axis=0))[0]
            if len(xs) < w * .95 or (len(xs) > 1 and np.diff(xs).max() > max_column_gap):
                continue
            core_columns=core[:,xs].any(axis=0)
            if core.sum()<40 or core_columns.mean()<.5:
                rejections.append(dict(roi=[sx.start,sy.start,sx.stop,sy.stop],reason='Too few strong hue seeds across the candidate.'))
                continue
            # Intersections can connect separate curves of the same hue. Reject
            # sustained separate vertical bands rather than tracing their envelope.
            separated=0
            for x in xs:
                column=np.where(pixels[:,x])[0]
                gaps=np.where(np.diff(column)>5)[0]
                if any(fill_support[sy.start+column[k]+1:sy.start+column[k+1],sx.start+x].mean()<.95 for k in gaps):
                    separated+=1
            multi=separated/len(xs)
            if multi>.25:
                rejections.append(dict(roi=[sx.start,sy.start,sx.stop,sy.stop],reason='Multiple separated bands share this colored component.',multiple_band_fraction=multi))
                continue
            # A thin stroke's upper edge moves far above its center on steep
            # segments. Euclidean thickness distinguishes a narrow strong
            # stroke from a broad solid area, including sparse filled peaks
            # whose global foreground density is small. Faint-only columns
            # retain the observed upper edge because they may contain fill.
            distances=ndimage.distance_transform_edt(core)
            radius=float(distances.max())
            typical_radius=float(np.median(distances[:,xs].max(axis=0)))
            # Two nearby stroke legs can double local thickness at a join.
            # Dense solid areas must not set their own permissive width limit.
            centerline=core.mean()<.1 and radius<=max(4.,2*typical_radius)
            ys=[]
            for x,has_core in zip(xs,core_columns):
                column=np.where(core[:,x] if has_core else pixels[:,x])[0]
                y=np.median(column) if centerline and has_core else column.min()
                ys.append(float(y+sy.start))
            ys=np.asarray(ys)
            if np.ptp(ys)<1:continue
            candidates.append(dict(color=color, roi=[sx.start, sy.start, sx.stop, sy.stop],
                                   x=(xs + sx.start).tolist(), y=ys.tolist(),
                                   pixel_error=np.where(core_columns,2.5,3.5).tolist(),
                                   trace_mode='thin_strong_stroke_center' if centerline else 'broad_strong_region_upper_edge',
                                   strong_inradius=radius,typical_strong_inradius=typical_radius,
                                   weak_column_fraction=float(1-core_columns.mean()),multiple_band_fraction=float(multi)))
    geometry = dict(image=str(image), size=list(im.size), roi=[0, 0, *im.size], series=[],
                    quality_issues=rejections, warnings=[], method='strong hue seeds with observed faint-pixel expansion; thin strong strokes use centers, broad regions and faint-only columns use upper edges; dilation groups only')
    if len(candidates) != 1:
        geometry['quality_issues'].append(dict(reason='Need exactly one wide colored curve.'))
        return geometry, candidates
    c = candidates[0]
    points = [dict(x=x,y=y,pixel_error=e) for x,y,e in zip(c['x'],c['y'],c['pixel_error'])]
    q = -np.asarray(c['y'])
    geometry.update(roi=c['roi'], series=[dict(id='series_0', kind='area', color=c['color'], points=points,
                                             coordinates=c['y'], shape_normalized=((q-q.min()) / np.ptp(q)).tolist(),
                                             weak_column_fraction=c['weak_column_fraction'],
                                             trace_mode=c['trace_mode'],strong_inradius=c['strong_inradius'],
                                             shape_note='Relative image geometry only; faint columns use observed pixels and a larger raster tolerance. The bottom edge is not a zero observation.')])
    return geometry, candidates


def date_axis(tokens, geometry, periods):
    """Infer one consistent dated text row; do not force endpoints to table ends."""
    points = geometry['series'][0]['points']
    left, right = points[0]['x'], points[-1]['x']
    image_width=geometry.get('size',[right+40])[0]
    bottom = max(p['y'] for p in points)
    by_month_day = {}
    for period in periods:
        by_month_day.setdefault(period[5:], []).append(period)
    labels = []
    for t in tokens:
        month = MONTHS.get(t['text'].lower())
        if not month:
            continue
        x, y, w, h = t['box']
        if not 0 <= x <= image_width or not bottom < _center(t)[1] < bottom + max(180, (right-left)*.3):
            continue
        near = [n for n in tokens if re.fullmatch(r'\d{1,2}', n['text'])
                and -1 <= n['box'][0]-x-w <= h*1.8
                and abs(_center(n)[1]-_center(t)[1]) < h*.65]
        if len(near) != 1:
            continue
        n = near[0]
        choices = by_month_day.get(f'{month:02d}-{int(n["text"]):02d}', [])
        if len(choices) != 1:
            continue
        labels.append(dict(date=choices[0], x=(x+n['box'][0]+n['box'][2])/2,
                           y=_center(t)[1], height=h, month_box=t['box'], day_box=n['box']))
    rows = []
    for label in sorted(labels, key=lambda t:t['y']):
        if rows and abs(label['y']-np.median([l['y'] for l in rows[-1]])) < 5:
            rows[-1].append(label)
        else:
            rows.append([label])
    rows = [sorted(r, key=lambda t:t['x']) for r in rows if len(r) >= 3]
    if len(rows) != 1:
        return dict(status='needs_review', reason='Need one row with at least three unambiguous month/day labels.', labels=labels)
    labels = rows[0]
    outside=[]
    for label in labels:
        width=label['day_box'][0]+label['day_box'][2]-label['month_box'][0]
        if label['x']+width/2+3<left or label['x']-width/2-3>right:outside.append(label)
    if outside:
        return dict(status='needs_review',reason='The trace does not cover the visible historical date-axis labels.',labels=labels,outside_trace=outside)
    axis_y = np.median([l['y'] for l in labels])
    curve_top = geometry['roi'][1]
    year_tokens = [t['text'] for t in tokens if re.search(r'20\d{2}', t['text'])
                   and left-40 <= _center(t)[0] <= right+40
                   and (abs(_center(t)[1]-axis_y)<35 or curve_top-140 < _center(t)[1] < curve_top)]
    if any(not re.fullmatch(r'20\d{2}', t) for t in year_tokens):
        return dict(status='needs_review', reason='An ambiguous year-like OCR token needs review.', labels=labels, year_tokens=year_tokens)
    years = set(year_tokens)
    if years and years != {l['date'][:4] for l in labels}:
        return dict(status='needs_review', reason='An explicit axis year contradicts the public table.', labels=labels)
    # Edge labels may be inset to keep their text inside the card. Fit only
    # labels whose centers fall inside the observed curve when enough remain;
    # retain exclusions. This choice uses geometry, never monetary values.
    inside = [l for l in labels if left+10 < l['x'] < right-10]
    excluded = [l for l in labels if l not in inside] if len(inside)>=5 else []
    fit_labels = inside if len(inside)>=5 else labels
    days = np.array([date.fromisoformat(l['date']).toordinal() for l in fit_labels], float)
    xs = np.array([l['x'] for l in fit_labels])
    if np.any(np.diff(days) <= 0) or len(set(days)) != len(days):
        return dict(status='needs_review', reason='Date labels are duplicated or out of order.', labels=labels)
    a, b = np.polyfit(days-days[0], xs, 1)
    residual = float(np.max(np.abs(xs-(a*(days-days[0])+b))))
    if a <= 0 or residual > max(4, (right-left)*.012):
        return dict(status='needs_review', reason='Date-label centers do not support a regular daily axis.', labels=labels, residual=residual)
    return dict(status='proposed', labels=labels, fit_labels=fit_labels, excluded_edge_labels=excluded,
                origin=fit_labels[0]['date'], pixels_per_day=float(a),
                origin_x=float(b), residual=residual,
                pixel_error=max(3., residual+1.),
                year_basis='explicit_axis_year' if years else 'unique_dates_in_linked_public_table',
                note='Interior text centers are assumed to approximate tick positions within max(3px, fit residual + 1px); output dates remain proposed rather than verified.')


def map_observations(geometry, rows, axis):
    points=geometry['series'][0]['points'];px=np.array([p['x'] for p in points]);py=np.array([p['y'] for p in points])
    pe=np.array([p.get('pixel_error',2.5) for p in points])
    origin=date.fromisoformat(axis['origin']).toordinal();observations=[]
    for row in rows:
        x=axis['origin_x']+axis['pixels_per_day']*(date.fromisoformat(row['period']).toordinal()-origin)
        o=dict(row,pixel_x=float(x),eligible=False)
        if x<px[0] or x>px[-1]:o['reason']='date_outside_trace'
        elif row['status']!='dated_observation':o['reason']=row['status']
        elif axis.get('sampling'):
            # A step's vertical stroke has no single observed daily value.
            # Keep the date position separate from the plateau measured for it.
            convention=axis['sampling']['convention'];step=axis['pixels_per_day']
            lo,hi={'pre':(-.4,-.18),'post':(.18,.4),'mid':(-.18,.18)}[convention]
            near=(px>=x+lo*step)&(px<=x+hi*step)
            if x+lo*step<px[0] or x+hi*step>px[-1] or near.sum()<4:
                o['reason']='No complete observed plateau window for this date.'
            elif np.ptp(py[near])>2.5:
                o['reason']='The proposed step sample is not a flat observed plateau.'
            else:
                y=float(np.median(py[near]))
                o.update(eligible=True,pixel=y,pixel_error=float(max(pe[near])+max(abs(py[near]-y))),
                         sample_x=float(np.median(px[near])),sample_window=[float(px[near][0]),float(px[near][-1])],
                         sampling_convention=convention)
        else:
            y=float(np.interp(x,px,py));dx=axis['pixel_error'];near=(px>=x-dx)&(px<=x+dx);ys=py[near]
            o.update(eligible=True,pixel=y,pixel_error=float(max(pe[near],default=2.5)+max(abs(ys-y),default=0.)))
        observations.append(o)
    return observations


def observation_anchors(rows):
    return [dict(pixel=r['pixel'],low=r['low'],high=r['high'],pixel_error=r['pixel_error'],
                 source=r['source'],source_line=r['source_line'],period=r['period'],matched=True,
                 correspondence_basis='conditional_external_table') for r in rows]


def checking_information(rows):
    """Checking one indistinguishable level cannot validate the axis slope.

Require two checking observations separated in both printed-value intervals and
pixel intervals. This only accepts or rejects the frozen checking set; it never
selects another split, alignment, source or scale using checking amounts.
"""
    for i,a in enumerate(rows):
        for b in rows[i+1:]:
            values_separated=a['high']<b['low'] or b['high']<a['low']
            pixels_separated=abs(a['pixel']-b['pixel'])>a['pixel_error']+b['pixel_error']
            if values_separated and pixels_separated:
                return dict(status='informative',distinct_dates=[a['period'],b['period']],
                            note='At least two checking levels are distinguishable in both value and pixel intervals; this does not guarantee hidden-value accuracy.')
    return dict(status='uninformative',reason='Unused checking dates do not contain two distinguishable value/pixel levels; agreement at one level cannot validate scale.')


def corner_alignment(geometry, axis):
    """Propose a daily grid from straight-segment joins, without source values.

    Side windows fit the two lines. Central pixels are withheld from those
    fits and test whether the join is sharp rather than a rounded extremum.
    The final grid must agree with all retained corners and printed labels.
    """
    points=geometry['series'][0]['points']
    xx=np.array([p['x'] for p in points]);yy=np.array([p['y'] for p in points])
    errors=np.array([p.get('pixel_error',2.5) for p in points])
    step=axis['pixels_per_day'];knots=[];rejected=[]
    first=int(np.ceil((xx[0]-axis['origin_x'])/step))
    last=int(np.floor((xx[-1]-axis['origin_x'])/step))
    for dt in range(first,last+1):
        x=axis['origin_x']+step*dt
        left=(xx>x-.4*step)&(xx<x-.18*step)
        right=(xx>x+.18*step)&(xx<x+.4*step)
        if min(left.sum(),right.sum())<4:continue
        l=np.polyfit(xx[left]-x,yy[left],1);r=np.polyfit(xx[right]-x,yy[right],1)
        residual=max(np.sqrt(np.mean((np.polyval(l,xx[left]-x)-yy[left])**2)),
                     np.sqrt(np.mean((np.polyval(r,xx[right]-x)-yy[right])**2)))
        delta=l[0]-r[0]
        if abs(delta)<.5 or residual>1.5:continue
        dx=(r[1]-l[1])/delta
        if abs(dx)>max(4.,.2*step):continue
        middle=(np.abs(xx-(x+dx))<=.15*step)&~left&~right
        if middle.sum()<3 or not np.any(xx[middle]<x+dx) or not np.any(xx[middle]>x+dx):continue
        mx=xx[middle]-x
        predicted=np.where(mx<=dx,np.polyval(l,mx),np.polyval(r,mx))
        center_error=float(np.median(np.abs(predicted-yy[middle])))
        tolerance=float(max(1.5,np.median(errors[middle])))
        node=dict(day_offset=dt,x=float(x+dx),side_rms=float(residual),
                  central_error=center_error,central_tolerance=tolerance,central_pixels=int(middle.sum()))
        if center_error>tolerance:
            rejected.append(dict(node,reason='Central pixels do not support the fitted sharp join.'));continue
        knots.append(node)
    ledger=dict(status='unsupported',knots=knots,rejected_joins=rejected,
                selection_uses='Image geometry and printed daily date labels only; no monetary values.')
    if len(knots)<4 or np.ptp([k['x'] for k in knots])<np.ptp(xx)*.5:
        ledger['reason']='Need four supported corners spanning at least half the trace.';return None,ledger
    a,b=np.polyfit([k['day_offset'] for k in knots],[k['x'] for k in knots],1)
    residual=max(abs(k['x']-(a*k['day_offset']+b)) for k in knots)
    ledger['grid_residual']=float(residual)
    if residual>2.5 or not .97<=a/step<=1.03 or abs(b-axis['origin_x'])>4:
        ledger['reason']='Corners do not support one regular grid within the existing text-axis adjustment limits.';return None,ledger
    origin=date.fromisoformat(axis['origin']).toordinal()
    for label in axis['fit_labels']:
        x=b+a*(date.fromisoformat(label['date']).toordinal()-origin)
        width=label['day_box'][0]+label['day_box'][2]-label['month_box'][0]
        if abs(x-label['x'])>width/2+3:
            ledger['reason']='Corner grid falls outside a printed date label envelope.';return None,ledger
    ledger['status']='proposed'
    proposed=dict(axis,pixels_per_day=float(a),origin_x=float(b),
        positional_hypothesis=dict(method='image_corners',slope_multiplier=float(a/step),
            offset_pixels=float(b-axis['origin_x']),
            note='Visible straight-segment joins are assumed to occur on daily sample positions; geometry selects the grid without monetary values.'))
    return proposed,ledger


def step_grids(geometry, axis):
    """Locate abrupt transitions between flat plateaus without source values.

    Integer-day boundaries admit pre/post conventions; half-day boundaries
    admit mid. The text-derived grid assigns dates, and every retained jump
    must support the same regular grid. Smooth/linear joins are not steps.
    """
    points=geometry['series'][0]['points']
    xx=np.array([p['x'] for p in points]);yy=np.array([p['y'] for p in points])
    step=axis['pixels_per_day'];knots=[]
    ledger=dict(status='not_step',knots=knots,grids=[],
                selection_uses='Transition geometry and printed dates locate the grid; only fitting dates select pre/post/mid.')
    if len(xx)<2 or step<12 or np.mean(abs(np.diff(yy))<=1)<.65:return [],ledger
    jumps=np.flatnonzero(abs(np.diff(yy))>1)
    groups=np.split(jumps,np.where(np.diff(xx[jumps])>max(4.,.14*step))[0]+1)
    for group in groups:
        if not len(group):continue
        a,b=xx[group[0]],xx[group[-1]+1];x=(a+b)/2
        if b-a>max(4.,.25*step):continue
        left=(xx>=x-.4*step)&(xx<=x-.18*step)
        right=(xx>=x+.18*step)&(xx<=x+.4*step)
        if min(left.sum(),right.sum())<4:continue
        if max(np.ptp(yy[left]),np.ptp(yy[right]))>2.5:continue
        ly,ry=float(np.median(yy[left])),float(np.median(yy[right]))
        if abs(ly-ry)<8:continue
        middle=yy[(xx>=a)&(xx<=b)]
        if middle.min()<min(ly,ry)-2.5 or middle.max()>max(ly,ry)+2.5:continue
        knots.append(dict(x=float(x),width=float(b-a),left_level=ly,right_level=ry))
    if len(knots)<4 or np.ptp([k['x'] for k in knots])<np.ptp(xx)*.5:return [],ledger
    ledger['status']='unsupported_grid';grids=[]
    origin=date.fromisoformat(axis['origin']).toordinal()
    for phase,conventions in ((0.,('pre','post')),(.5,('mid',))):
        positions=np.array([k['x'] for k in knots])
        offsets=np.round((positions-axis['origin_x'])/step-phase)+phase
        a,b=np.polyfit(offsets,positions,1)
        residual=float(np.max(abs(positions-(a*offsets+b))))
        entry=dict(phase=phase,residual=residual,status='unsupported');ledger['grids'].append(entry)
        if len(set(offsets))!=len(offsets) or residual>2.5 or not .97<=a/step<=1.03 or abs(b-axis['origin_x'])>4:continue
        labels_ok=True
        for label in axis['fit_labels']:
            x=b+a*(date.fromisoformat(label['date']).toordinal()-origin)
            width=label['day_box'][0]+label['day_box'][2]-label['month_box'][0]
            if abs(x-label['x'])>width/2+3:labels_ok=False
        if not labels_ok:continue
        entry.update(status='proposed',origin_x=float(b),pixels_per_day=float(a))
        for convention in conventions:
            grids.append(dict(axis,origin_x=float(b),pixels_per_day=float(a),
                sampling=dict(convention=convention),
                positional_hypothesis=dict(method='image_steps',slope_multiplier=float(a/step),offset_pixels=float(b-axis['origin_x']),
                    note='Flat plateaus and abrupt transitions locate daily positions; fitting dates select the plateau convention. Date identity remains conditional.')))
    if grids:ledger['status']='proposed'
    return grids,ledger


def select_step_alignment(geometry, rows, grids, search):
    """Require one identifiable convention using the original fitting split."""
    training=[r for r in rows if date.fromisoformat(r['period']).toordinal()%3!=1]
    ledger=dict(strategy='image_steps',step_search=search,trials=[],selected=None,
                selection_uses=search['selection_uses']);passing=[]
    for axis in grids:
        obs=[r for r in map_observations(geometry,training,axis) if r['eligible']]
        entry=dict(convention=axis['sampling']['convention'],fit_dates=[r['period'] for r in obs],status='insufficient_fitting_dates')
        ledger['trials'].append(entry)
        if len(obs)<8:continue
        fit=calibrate([r['pixel'] for r in obs],observation_anchors(obs),scale='unknown',pixel_error=max(r['pixel_error'] for r in obs))
        entry['status']=fit['status']
        if fit['status']!='calibrated':continue
        values=np.array([r['value'] for r in obs]);span=float(np.ptp(values))
        error=float(np.mean(abs(np.array(fit['values'])-values))/max(span,1.))
        entry.update(fit_nmae=error,scale=fit['scale'])
        if span>0 and error<.02:passing.append((axis,len(ledger['trials'])-1))
    if len(passing)!=1:
        ledger['reason']='Step geometry and fitting dates do not identify exactly one daily sampling convention.'
        return None,ledger
    selected,index=passing[0];ledger['selected']=index
    return selected,ledger


def select_alignment(geometry, rows, axis):
    """Choose a limited positional hypothesis using fitting dates only.

    Prefer supported step boundaries, then image corners; otherwise use the fitting-date
    search. The strategy is fixed before numerical checking. Checking values
    never choose a strategy, offset, slope, axis model or objective.
    """
    grids,step_search=step_grids(geometry,axis)
    if step_search['status']!='not_step':
        return select_step_alignment(geometry,rows,grids,step_search)
    geometric,corner_search=corner_alignment(geometry,axis)
    if geometric is not None:
        return geometric,dict(strategy='image_corners',corner_search=corner_search,
            trials=[dict(status='proposed',method='image_corners')],selected=0,
            selection_uses=corner_search['selection_uses'])
    training=[r for r in rows if date.fromisoformat(r['period']).toordinal()%3!=1]
    origin=date.fromisoformat(axis['origin']).toordinal();trials=[];best=None
    for multiplier in (1.,.995,1.005,.99,1.01,.985,1.015,.98,1.02,.975,1.025,.97,1.03):
        for offset in (0.,-2.,2.,-4.,4.):
            trial=dict(axis,pixels_per_day=axis['pixels_per_day']*multiplier,origin_x=axis['origin_x']+offset)
            # All retained labels must still fit within their rendered text
            # extent plus three pixels; nothing is moved beyond this envelope.
            displacements=[]
            for label in axis['fit_labels']:
                x=trial['origin_x']+trial['pixels_per_day']*(date.fromisoformat(label['date']).toordinal()-origin)
                width=label['day_box'][0]+label['day_box'][2]-label['month_box'][0]
                displacements.append(abs(x-label['x'])<=width/2+3)
            if not all(displacements):continue
            obs=[r for r in map_observations(geometry,training,trial) if r['eligible']]
            entry=dict(slope_multiplier=multiplier,offset_pixels=offset,fit_dates=[r['period'] for r in obs])
            if len(obs)<8:
                entry['status']='insufficient_fitting_dates';trials.append(entry);continue
            fit=calibrate([r['pixel'] for r in obs],observation_anchors(obs),scale='unknown',pixel_error=max(r['pixel_error'] for r in obs))
            entry['status']=fit['status']
            if fit['status']=='calibrated':
                values=np.array([r['value'] for r in obs]);span=float(np.ptp(values))
                error=float(np.mean(np.abs(np.array(fit['values'])-values))/max(span,1.))
                entry.update(fit_nmae=error,scale=fit['scale'])
                if span>0 and error<.02 and (best is None or error<best[0]):best=(error,trial,len(trials))
            trials.append(entry)
    ledger=dict(strategy='fitting_dates',corner_search=corner_search,trials=trials,
                selection_uses='fitting dates only; no checking or withheld values',selected=None)
    if best is None:return None,ledger
    _,selected,index=best;ledger['selected']=index
    selected['positional_hypothesis']=dict(method='fitting_dates',slope_multiplier=trials[index]['slope_multiplier'],offset_pixels=trials[index]['offset_pixels'],
        note='Limited image/table alignment selected using fitting dates; text positions are approximate, not verified exact tick locations.')
    return selected,ledger


def recover_external(image, profile, output):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    geometry, candidates = trace_curve(image)
    scans = [read_text(image, scale=s) for s in (2., 3.)]
    tokens, disagreements = consensus_tokens(scans[0]['tokens'], scans[1]['tokens'])
    result = dict(image=str(image), image_sha256=hashlib.sha256(Path(image).read_bytes()).hexdigest(),
                  status='needs_evidence_or_review', geometry=geometry, curve_candidates=candidates,
                  profile_source=profile['source'], profile_sha256=profile['source_sha256'],
                  ocr=scans, consensus_tokens=tokens, ocr_disagreements=disagreements,
                  reasons=[], assumptions=[], observations=[], recovery=[], date_assignment='proposed_unverified')
    if len(geometry['series']) != 1 or geometry['quality_issues']:
        result['reasons'].append('No unique complete curve.')
    tables = [t for t in profile['tables'] if t['aggregation'] == 'daily_total']
    if len(tables) != 1:
        result['reasons'].append('Need a dated daily-revenue table.')
    text = ' '.join(t['text'] for t in tokens)
    if not re.search(r'(?<!\w)'+re.escape(profile['entity'])+r'(?!\w)', text, re.I):
        result['reasons'].append('The public profile name was not read in the chart image.')
    if not result['reasons']:
        series = geometry['series'][0]
        left, top, right, _ = geometry['roi']
        # A nearby explicit Revenue selector is required; no substitution of an
        # MRR headline, all-time aggregate, or website-wide company name.
        headings = [t for t in tokens if t['text'].lower() in ('revenue','mrr','arr')
                    and left-50 <= _center(t)[0] <= right+30 and top-140 < _center(t)[1] < top-5]
        if len(headings) != 1 or headings[0]['text'].lower() != 'revenue':
            result['reasons'].append('Need a unique nearby Revenue heading; other metrics are not interchangeable.')
        else:
            hy = _center(headings[0])[1]
            qualifiers = [t['text'].lower() for t in tokens if abs(_center(t)[1]-hy)<12]
            if set(qualifiers) & {'monthly','annual','cumulative','gross','net','forecast','target','mrr','arr'}:
                result['reasons'].append('A local metric qualifier conflicts with daily revenue.')
        axis = date_axis(tokens, geometry, [r['period'] for r in tables[0]['rows'] if not r['partial']])
        result['date_axis'] = axis
        if axis['status'] != 'proposed':
            result['reasons'].append(axis['reason'])
    if not result['reasons']:
        result['image_date_axis']=axis
        selected,ledger=select_alignment(geometry,tables[0]['rows'],axis)
        result['alignment_search']=ledger
        if selected is None:result['reasons'].append('No text-constrained positional hypothesis identifies a unique consistent scale from fitting dates.')
        else:axis=selected;result['date_axis']=axis
    if not result['reasons']:
        result['observations']=map_observations(geometry,tables[0]['rows'],axis)
        usable = [r for r in result['observations'] if r['eligible']]
        # The split is fixed by date ordinal before reading or fitting values.
        fitting = [r for r in usable if date.fromisoformat(r['period']).toordinal()%3 != 1]
        checking = [r for r in usable if date.fromisoformat(r['period']).toordinal()%3 == 1]
        result['split'] = dict(fit_dates=[r['period'] for r in fitting], check_dates=[r['period'] for r in checking])
        result['checking_information']=checking_information(checking)
        if len(fitting) < 8 or len(checking) < 5:
            result['reasons'].append('Need at least eight fitting and five unused checking dates.')
        elif result['checking_information']['status']!='informative':
            result['reasons'].append(result['checking_information']['reason'])
        else:
            anchors = observation_anchors
            fit = calibrate([r['pixel'] for r in checking], anchors(fitting), scale='unknown',
                            pixel_error=max(r['pixel_error'] for r in checking))
            result['checking_fit'] = fit
            if fit['status'] != 'calibrated':
                result['reasons'].append('Fitting dates do not identify a unique consistent axis scale.')
            else:
                truth = np.array([r['value'] for r in checking])
                span = np.ptp([r['value'] for r in usable])
                error = float(np.mean(np.abs(np.array(fit['values'])-truth))/max(span,1.))
                coverage = float(np.mean((truth>=np.array(fit['lower'])) & (truth<=np.array(fit['upper']))))
                result['checking'] = dict(nmae=error, interval_coverage=coverage, count=len(checking))
                if span <= 0 or error >= .02 or coverage < .9:
                    result['reasons'].append('Unused checking dates fail the fixed 2% NMAE / 90% coverage criteria.')
                else:
                    cal = calibrate(series['coordinates'], anchors(usable), scale='unknown',
                                    pixel_error=max(r['pixel_error'] for r in usable))
                    if cal['status'] != 'calibrated':
                        result['reasons'].append('All evidence does not identify one consistent scale.')
                    else:
                        cal['status'] = 'conditional_calibration'
                        alignment_assumption={
                            'image_steps':'Visible step boundaries locate a regular daily grid; fitting dates select the pre/post/mid plateau convention. Daily estimates measure flat plateau windows, never vertical-stroke midpoints.',
                            'image_corners':'Visible straight-segment joins are assumed to mark daily sample positions; the date grid was selected from image geometry without monetary values.',
                            'fitting_dates':'A small offset and spacing adjustment was selected with fitting dates inside the image text-box envelope; checking dates were not used to select it.'
                        }[axis['positional_hypothesis']['method']]
                        result.update(status='conditional_calibration',recovery=[dict(series='series_0',**cal)],
                                      assumptions=['The image and linked public profile describe the same entity and daily revenue definition.',
                                                   'The chart reporting year matches the uniquely matched dates in the public table.',
                                                   'Month/day text centers approximate a regular daily axis; their residual enters pixel uncertainty.',
                                                   alignment_assumption,
                                                   'Matching numerical patterns do not prove identity or source truth.',
                                                   'The public table uses UTC days; the image is assumed to use the same daily boundary.'])
                        if axis.get('sampling'):
                            # Predict every visible daily position, including dates
                            # absent from the source. Their source amounts are never
                            # consulted or changed into calibration observations.
                            points=series['points'];base=date.fromisoformat(axis['origin']).toordinal()
                            first=int(np.ceil((points[0]['x']-axis['origin_x'])/axis['pixels_per_day']))
                            last=int(np.floor((points[-1]['x']-axis['origin_x'])/axis['pixels_per_day']))
                            periods=[dict(period=date.fromordinal(base+dt).isoformat(),status='dated_observation') for dt in range(first,last+1)]
                            samples=[r for r in map_observations(geometry,periods,axis) if r['eligible']]
                            daily=calibrate([r['pixel'] for r in samples],anchors(usable),scale=cal['scale'],
                                            pixel_error=max((r['pixel_error'] for r in samples),default=2.5))
                            if daily['status']=='calibrated':
                                result['daily_recovery']=[dict(proposed_date=r['period'],pixel_x=r['pixel_x'],pixel_y=r['pixel'],
                                    sample_x=r['sample_x'],sample_window=r['sample_window'],sampling_convention=r['sampling_convention'],
                                    conditional_value=v,lower=lo,upper=hi,status='conditional_calibration',date_assignment='proposed_unverified')
                                    for r,v,lo,hi in zip(samples,daily['values'],daily['lower'],daily['upper'])]
    (out/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False), encoding="utf-8")
    overlay(image,geometry,out/'overlay.png')
    with (out/'data.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['point','relative_position','proposed_date','pixel_x','pixel_y','conditional_value','lower','upper','status'])
        if result['status']=='conditional_calibration':
            cal=result['recovery'][0];points=geometry['series'][0]['points'];axis=result['date_axis']
            for i,p in enumerate(points):
                # Each traced pixel is a curve sample, not a daily accounting row.
                w.writerow([i,(p['x']-points[0]['x'])/(points[-1]['x']-points[0]['x']),'',p['x'],p['y'],
                            cal['values'][i],cal['lower'][i],cal['upper'][i],result['status']])
    if result.get('daily_recovery'):
        with (out/'daily.csv').open('w',newline='') as f:
            fields=['proposed_date','pixel_x','pixel_y','sample_x','sample_window','sampling_convention',
                    'conditional_value','lower','upper','status','date_assignment']
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(result['daily_recovery'])
    return result
