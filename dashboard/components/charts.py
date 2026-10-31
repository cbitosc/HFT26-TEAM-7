"""
charts.py - inline SVG/HTML charts in the SmallWorld style (no iframes, no JS).
Every function returns an HTML string; render it with ui.html().
"""

AMBER, TEAL, SAGE = "#fbbb5b", "#a6cfc5", "#b1ceae"
LOWEST, HIGHEST, OUTLINE, ON = "#06100e", "#2d3734", "#8b928f", "#dae5e1"
GROUP_COLORS = {"carnivore": AMBER, "herbivore": TEAL, "avian": SAGE}
MONO = "font-family:'JetBrains Mono',monospace"


def circadian(hourly: list[dict], names: dict | None = None, height: int = 230) -> str:
    """24 stacked hourly columns (carnivore / herbivore / avian) over diel shading."""
    W, H = 720, height
    totals = [sum(d[g] for g in GROUP_COLORS) for d in hourly]
    peak = max(totals) or 1
    slot = W / 24
    bw = slot * 0.62
    svg = []
    # diel bands: night 0-5, dawn 5-8, day 8-17, dusk 17-20, night 20-24
    for a, b, fill, op in [(0, 5, "#0e1a17", .9), (5, 8, AMBER, .05), (17, 20, AMBER, .05), (20, 24, "#0e1a17", .9)]:
        svg.append(f'<rect x="{a*slot:.1f}" y="0" width="{(b-a)*slot:.1f}" height="{H}" fill="{fill}" fill-opacity="{op}"/>')
    for f in (.25, .5, .75):
        svg.append(f'<line x1="0" x2="{W}" y1="{H*f:.0f}" y2="{H*f:.0f}" stroke="{HIGHEST}" stroke-dasharray="2 4"/>')
    for d, tot in zip(hourly, totals):
        x = d["hour"] * slot + (slot - bw) / 2
        y = H
        for g in ("herbivore", "avian", "carnivore"):          # carnivores on top, like the design
            v = d[g]
            if not v:
                continue
            h = v / peak * (H - 34)
            y -= h
            svg.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="1.5" '
                       f'fill="{GROUP_COLORS[g]}" fill-opacity="{0.92 if g == "carnivore" else 0.8}">'
                       f'<title>{d["hour"]:02d}:00 · {g}: {v}</title></rect>')
        if tot == 0:
            svg.append(f'<rect x="{x:.1f}" y="{H-2}" width="{bw:.1f}" height="2" fill="{HIGHEST}"/>')

    # peak annotations
    tags = []
    def tag(group, label, top):
        vals = [d[group] for d in hourly]
        if group == "herbivore":
            vals = [d["herbivore"] + d["avian"] for d in hourly]
        if max(vals) == 0:
            return
        h = vals.index(max(vals))
        left = min(max(h / 24 * 100, 1), 70)
        who = f" ({names[group]})" if names and names.get(group) else ""
        col = AMBER if group == "carnivore" else SAGE
        tags.append(f'<div style="position:absolute;top:{top}px;left:{left:.1f}%;background:rgba(34,44,42,.92);'
                    f'border-radius:4px;padding:3px 9px;display:flex;align-items:center;gap:6px;white-space:nowrap;'
                    f'box-shadow:0 4px 12px rgba(0,0,0,.35)"><span style="width:6px;height:6px;border-radius:50%;'
                    f'background:{col}"></span><span style="{MONO};font-size:10px;color:{col};font-weight:600">'
                    f'{label}: {h:02d}:00{who}</span></div>')
    tag("carnivore", "Peak Carnivora", 10)
    tag("herbivore", "Peak Herbivore/Avian", 40)

    labels = "".join(f'<span style="{MONO};font-size:10px;color:{OUTLINE}">{t}</span>' for t in
                     ["00:00", "03:00", "06:00 (Dawn)", "09:00", "12:00 (Noon)", "15:00", "18:00 (Dusk)", "21:00", "23:00"])
    return (f'<div style="position:relative;background:{LOWEST};border-radius:4px;padding:12px 12px 8px 12px">'
            f'{"".join(tags)}'
            f'<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" style="width:100%;height:{H}px;display:block">'
            f'{"".join(svg)}</svg>'
            f'<div style="display:flex;justify-content:space-between;margin-top:8px">{labels}</div></div>')


def donut(noct: float, crep: float, diur: float, size: int = 120) -> str:
    """Diel photoperiod ring."""
    segs, off = [], 25.0      # start at 12 o'clock
    for pct, col in ((noct, AMBER), (crep, TEAL), (diur, SAGE)):
        if pct > 0:
            segs.append(f'<circle cx="21" cy="21" r="15.915" fill="none" stroke="{col}" stroke-width="5" '
                        f'stroke-dasharray="{max(pct-0.6, 0.1):.2f} {100-max(pct-0.6, 0.1):.2f}" stroke-dashoffset="{off:.2f}"/>')
        off -= pct
    return (f'<div style="position:relative;width:{size}px;height:{size}px;flex-shrink:0">'
            f'<svg viewBox="0 0 42 42" width="{size}" height="{size}">'
            f'<circle cx="21" cy="21" r="15.915" fill="none" stroke="{HIGHEST}" stroke-width="5"/>{"".join(segs)}</svg>'
            f'<div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center">'
            f'<span style="font-family:Geist,sans-serif;font-size:19px;font-weight:700;color:{AMBER}">{noct:.1f}%</span>'
            f'<span style="{MONO};font-size:8.5px;letter-spacing:.08em;color:{OUTLINE}">NOCTURNAL</span></div></div>')


def _fmt_month(m: str) -> str:
    import calendar
    y, mm = m.split("-")
    return f"{calendar.month_abbr[int(mm)]} '{y[2:]}"


def sparkline(series: list[dict], height: int = 110) -> str:
    """Smoothed area trend of monthly independent encounters."""
    if len(series) < 2:
        return (f'<div class="sw-inset" style="height:{height}px;display:flex;align-items:center;justify-content:center">'
                f'<span class="sw-sub">Not enough months of data for a trend yet</span></div>')
    W, H = 320, height
    vals = [d["count"] for d in series]
    mx = max(vals) or 1
    n = len(vals)
    pts = [(i / (n - 1) * W, H - 6 - v / mx * (H - 16)) for i, v in enumerate(vals)]
    path = f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        cx = (x0 + x1) / 2
        path += f" C {cx:.1f} {y0:.1f}, {cx:.1f} {y1:.1f}, {x1:.1f} {y1:.1f}"
    area = path + f" L {W} {H} L 0 {H} Z"
    peak_i = vals.index(mx)
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{3 if i in (peak_i, n-1) else 0}" '
                   f'fill="{AMBER if i == peak_i else TEAL}" vector-effect="non-scaling-stroke"/>'
                   for i, (x, y) in enumerate(pts))
    step = max(1, (n - 1) // 5)
    ticks = sorted(set(list(range(0, n, step)) + [n - 1]))
    if len(ticks) > 1 and ticks[-1] - ticks[-2] < step / 2:
        ticks.pop(-2)
    labels = "".join(f'<span style="{MONO};font-size:10px;color:{ON if i == n-1 else OUTLINE}">{_fmt_month(series[i]["month"])}</span>'
                     for i in ticks)
    return (f'<div class="sw-inset" style="padding:10px 12px">'
            f'<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" style="width:100%;height:{H}px;display:block;overflow:visible">'
            f'<defs><linearGradient id="swTrend" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="{TEAL}" stop-opacity=".35"/>'
            f'<stop offset="100%" stop-color="{TEAL}" stop-opacity="0"/></linearGradient></defs>'
            f'<path d="{area}" fill="url(#swTrend)"/><path d="{path}" fill="none" stroke="{TEAL}" stroke-width="2" '
            f'vector-effect="non-scaling-stroke"/>{dots}</svg>'
            f'<div style="display:flex;justify-content:space-between;margin-top:6px">{labels}</div></div>')


def meter(label: str, pct: float, value: str, color: str = SAGE) -> str:
    """Labelled progress bar used in benchmark cards."""
    return (f'<div style="margin-top:14px"><div style="display:flex;justify-content:space-between;align-items:baseline">'
            f'<span class="sw-label">{label}</span><span style="{MONO};font-size:12px;font-weight:700;color:{ON}">{value}</span></div>'
            f'<div class="sw-bar" style="margin-top:6px"><div style="width:{max(0, min(pct, 100)):.1f}%;background:{color}"></div></div></div>')


def hbars(rows: list[tuple], max_val: float | None = None, color: str = TEAL) -> str:
    """Horizontal bar list: rows = [(label_html, value, value_text, color_or_None), ...]."""
    mx = max_val or max((r[1] for r in rows), default=1) or 1
    out = []
    for label, v, txt, col in rows:
        out.append(f'<div style="display:grid;grid-template-columns:minmax(120px,190px) 1fr 56px;gap:12px;align-items:center;margin:7px 0">'
                   f'<div style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{label}</div>'
                   f'<div class="sw-bar" style="height:8px"><div style="width:{v/mx*100:.1f}%;background:{col or color}"></div></div>'
                   f'<div style="{MONO};font-size:12px;text-align:right;color:{ON}">{txt}</div></div>')
    return "".join(out)


def heatmap(matrix: dict, row_labels: list[tuple], height_px: int = 22) -> str:
    """Species × hour heat grid. matrix[key] = 24 ints; row_labels = [(key, label_html), ...]."""
    mx = max((max(v) for v in matrix.values()), default=1) or 1
    head = "".join(f'<div style="{MONO};font-size:9px;color:{OUTLINE};text-align:center">{h:02d}</div>' for h in range(0, 24))
    rows = [f'<div></div>{head}']
    for key, label in row_labels:
        cells = "".join(
            f'<div title="{h:02d}:00 · {v}" style="height:{height_px}px;border-radius:2px;'
            f'background:{AMBER if v and v/mx > .66 else TEAL if v else HIGHEST};opacity:{(0.25 + 0.75*v/mx) if v else 0.35:.2f}"></div>'
            for h, v in enumerate(matrix[key]))
        rows.append(f'<div style="font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding-right:8px">{label}</div>{cells}')
    return (f'<div style="display:grid;grid-template-columns:170px repeat(24,1fr);gap:3px;align-items:center">'
            f'{"".join(rows)}</div>')


def columns(series: list[tuple], height: int = 140, color: str = TEAL) -> str:
    """Simple vertical column chart: series = [(label, value), ...]."""
    if not series:
        return ""
    mx = max(v for _, v in series) or 1
    n = len(series)
    bars = "".join(f'<div style="display:flex;flex-direction:column;justify-content:flex-end;align-items:center;height:100%;gap:4px" '
                   f'title="{lab}: {v}"><div style="width:70%;max-width:26px;height:{v/mx*100:.1f}%;min-height:{2 if v else 0}px;'
                   f'background:{color};border-radius:2px 2px 0 0"></div></div>' for lab, v in series)
    step = max(1, n // 8)
    labels = "".join(f'<div style="{MONO};font-size:9.5px;color:{OUTLINE};text-align:center;overflow:hidden">'
                     f'{lab if i % step == 0 else ""}</div>' for i, (lab, _) in enumerate(series))
    return (f'<div class="sw-inset"><div style="display:grid;grid-template-columns:repeat({n},1fr);height:{height}px;'
            f'border-bottom:1px solid {HIGHEST}">{bars}</div>'
            f'<div style="display:grid;grid-template-columns:repeat({n},1fr);margin-top:6px">{labels}</div></div>')
