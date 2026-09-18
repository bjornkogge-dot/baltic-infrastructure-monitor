import streamlit as st
import pandas as pd
import requests, xml.etree.ElementTree as ET
import plotly.graph_objects as go
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="Baltic / High North Intelligence", page_icon="◉", layout="wide")
st.markdown("""
<style>
.stApp{background:#050c12;color:#e8f0f5}.block-container{padding:0.8rem 1.2rem 1.2rem;max-width:1800px}
[data-testid="stSidebar"]{background:#07131c}
[data-testid="stMetric"]{background:#0a1720;border:1px solid #1c3443;border-radius:7px;padding:10px}
.panel{background:#0a1720;border:1px solid #1c3443;border-radius:7px;padding:13px;margin-bottom:9px}
.kicker{color:#7794a5;font-size:.72rem;letter-spacing:.15em;font-weight:800}
.event{background:#0a1720;border-left:3px solid #607d8b;padding:10px 12px;margin:7px 0;border-radius:4px}
.critical{border-left-color:#ff5b5b}.warning{border-left-color:#ffb454}.info{border-left-color:#65a9ff}
.small{color:#91a8b6;font-size:.80rem}.status{font-size:.69rem;letter-spacing:.09em;font-weight:800;border:1px solid #456173;padding:3px 5px;border-radius:4px}
</style>""",unsafe_allow_html=True)

UA={"User-Agent":"BalticHighNorthIntelligence/2.0 demo"}
AIS="https://meri.digitraffic.fi/api/ais/v1/locations"
META="https://meri.digitraffic.fi/api/ais/v1/vessels"
EMOD="https://ows.emodnet-humanactivities.eu/wfs"

def gj(url,params=None,t=20):
    r=requests.get(url,params=params,headers=UA,timeout=t); r.raise_for_status(); return r.json()

@st.cache_data(ttl=60)
def ais_live():
    loc=gj(AIS); meta=gj(META)
    rows=[]
    for f in loc.get("features",[]):
        p=f.get("properties",{}); c=(f.get("geometry") or {}).get("coordinates",[None,None])
        rows.append({"mmsi":str(p.get("mmsi",f.get("mmsi",""))),"lon":c[0],"lat":c[1],
                     "sog":p.get("sog"),"cog":p.get("cog"),"time":p.get("timestamp") or p.get("time")})
    d=pd.DataFrame(rows).dropna(subset=["lat","lon"])
    items=(meta.get("vessels") or meta.get("features") or meta.get("data") or []) if isinstance(meta,dict) else meta
    md=[]
    for x in items:
        p=x.get("properties",x)
        md.append({"mmsi":str(p.get("mmsi","")),"name":p.get("name") or "Unknown",
                   "imo":p.get("imo"),"destination":p.get("destination")})
    if md: d=d.merge(pd.DataFrame(md),on="mmsi",how="left")
    if "name" not in d: d["name"]="Unknown"
    d["name"]=d["name"].fillna("Unknown")
    return d

@st.cache_data(ttl=3600)
def catalog():
    r=requests.get(EMOD,params={"service":"WFS","request":"GetCapabilities","version":"2.0.0"},headers=UA,timeout=25)
    r.raise_for_status(); root=ET.fromstring(r.content); out=[]
    for ft in root.iter():
        if not ft.tag.endswith("FeatureType"): continue
        name=title=None
        for ch in ft:
            if ch.tag.endswith("Name"): name=ch.text
            if ch.tag.endswith("Title"): title=ch.text
        if name: out.append((name,title or name))
    return out

def score(item,kind):
    h=(" ".join(item)).lower()
    if kind=="cable":
        return 8*("actual" in h)+7*("telecommunication" in h)+5*("cable" in h)-7*("landing" in h)-3*("schematic" in h)
    return 7*("pipeline" in h)+3*("offshore" in h)

@st.cache_data(ttl=1800)
def emod(kind):
    ranked=sorted(catalog(),key=lambda x:score(x,kind),reverse=True)
    for name,title in [x for x in ranked if score(x,kind)>0][:8]:
        try:
            data=gj(EMOD,{"service":"WFS","version":"1.1.0","request":"GetFeature","typeName":name,
                          "bbox":"18,54,31,66","outputFormat":"application/json","maxFeatures":2500,
                          "srsName":"EPSG:4326"},30)
            fs=data.get("features",[])
            if fs:return fs,title
        except: pass
    return [],None

def lines(f):
    g=f.get("geometry") or {}; c=g.get("coordinates"); typ=g.get("type"); out=[]
    if typ=="LineString": return [c]
    if typ=="MultiLineString": return c
    return out

st.markdown('<div class="kicker">BALTIC / HIGH NORTH • OPERATIONAL INTELLIGENCE</div>',unsafe_allow_html=True)
c1,c2=st.columns([5,1])
with c1: st.markdown("# COMMON OPERATING PICTURE")
with c2: st.markdown("### LIVE ●")
st.caption("v2.0 • Open-source data fusion • Map + Intelligence Feed + Timeline + Investigation")

with st.sidebar:
    st.markdown("### LAYERS")
    la=st.toggle("🚢 Vessels / AIS",True)
    lc=st.toggle("━ Subsea cables",True)
    lp=st.toggle("━ Pipelines",False)
    st.toggle("⚓ Ports",False,disabled=True)
    st.toggle("🌊 Sea state",False,disabled=True)
    st.toggle("📡 Network",False,disabled=True)
    st.toggle("📰 OSINT events",False,disabled=True)
    st.divider()
    st.markdown("### MODE")
    mode=st.radio("Mode",["LIVE NOW","REPLAY INCIDENT"],label_visibility="collapsed")
    st.divider()
    st.markdown("### ANALYSIS")
    maxv=st.slider("Max AIS observations",200,3000,1400,100)
    st.caption("Disabled layers show the planned v2.x integration surface.")

try: vessels=ais_live().head(maxv) if la else pd.DataFrame()
except: vessels=pd.DataFrame()
try: cables,ctitle=emod("cable") if lc else ([],None)
except: cables,ctitle=[],None
try: pipes,ptitle=emod("pipeline") if lp else ([],None)
except: pipes,ptitle=[],None

m1,m2,m3,m4=st.columns(4)
m1.metric("VESSEL OBSERVATIONS",f"{len(vessels):,}")
m2.metric("CABLE LAYER","ONLINE" if cables else "OFFLINE")
m3.metric("ACTIVE INCIDENTS","DEMO 3")
m4.metric("MODE",mode)

mapcol,feed=st.columns([2.6,1],gap="medium")
with mapcol:
    fig=go.Figure()
    if len(vessels):
        fig.add_trace(go.Scattermap(lat=vessels.lat,lon=vessels.lon,mode="markers",marker={"size":6},
            name="Live AIS",text=vessels.apply(lambda r:f"<b>{r.get('name','Unknown')}</b><br>MMSI {r.mmsi}<br>SOG {r.get('sog','?')} kn<br>COG {r.get('cog','?')}°",axis=1),
            hovertemplate="%{text}<extra></extra>"))
    for fs,label,width in [(cables,"Subsea cable",6),(pipes,"Pipeline",5)]:
        first=True
        for f in fs[:400]:
            for line in lines(f):
                if line:
                    fig.add_trace(go.Scattermap(lat=[p[1] for p in line],lon=[p[0] for p in line],mode="lines",
                        line={"width":width},name=label,showlegend=first,hovertemplate=f"<b>{label}</b><extra></extra>"))
                    first=False
    # synthetic incident markers, explicitly labelled
    demo=pd.DataFrame([
        ["DEMO-01","Infrastructure disruption",59.88,24.75],
        ["DEMO-02","Navigation anomaly",60.08,25.30],
        ["DEMO-03","Maritime review event",59.55,23.85]],columns=["id","event","lat","lon"])
    fig.add_trace(go.Scattermap(lat=demo.lat,lon=demo.lon,mode="markers",marker={"size":15},
        name="Synthetic demo events",text=demo.event,hovertemplate="<b>SYNTHETIC EVENT</b><br>%{text}<extra></extra>"))
    fig.update_layout(map={"style":"carto-darkmatter","center":{"lat":59.8,"lon":24.6},"zoom":5.3},
        height=680,margin={"l":0,"r":0,"t":0,"b":0},paper_bgcolor="#050c12",font={"color":"#e8f0f5"},
        legend={"orientation":"h","y":0.01,"x":0.01})
    st.plotly_chart(fig,use_container_width=True)

with feed:
    st.markdown("### INTELLIGENCE FEED")
    st.markdown("""<div class="event critical"><span class="status">DEMO • CRITICAL</span><br><br>
    <b>Infrastructure disruption</b><br><span class="small">14:38 UTC • Gulf of Finland</span><br><br>
    Multi-source review initiated.<br><span class="small">Confidence: DEMO</span></div>""",unsafe_allow_html=True)
    st.markdown("""<div class="event warning"><span class="status">DEMO • REVIEW</span><br><br>
    <b>Maritime movement indicator</b><br><span class="small">14:31 UTC • Monitoring zone</span><br><br>
    Proximity + movement rule triggered.<br><span class="small">Attribution: NOT ESTABLISHED</span></div>""",unsafe_allow_html=True)
    st.markdown("""<div class="event info"><span class="status">SOURCE</span><br><br>
    <b>Open-data layer update</b><br><span class="small">14:24 UTC</span><br><br>
    AIS and infrastructure layers refreshed.</div>""",unsafe_allow_html=True)
    st.markdown("### WHAT CHANGED?")
    st.markdown("""<div class="panel"><b>Since previous review</b><br><br>
    3 demo incidents<br>1 infrastructure review<br>1 maritime indicator<br>1 source-layer update<br><br>
    <span class="small">This summary is synthetic in v2.0 and demonstrates the future alert workflow.</span></div>""",unsafe_allow_html=True)

st.markdown("### TIMELINE")
hours=["12:00","13:00","14:00","15:00","NOW"]
idx=st.select_slider("Operational time",options=hours,value="NOW",label_visibility="collapsed")
st.caption(f"Viewing: {idx}. In LIVE NOW, AIS remains current; the timeline demonstrates the planned replay interaction.")

st.divider()
a,b=st.columns([1.25,1])
with a:
    st.markdown("### INCIDENT INVESTIGATION")
    st.markdown("""<div class="panel"><span class="status">DEMO-01 • CORROBORATION WORKFLOW</span><br><br>
    <b>SUBSEA INFRASTRUCTURE DISRUPTION</b><br><span class="small">Gulf of Finland • synthetic scenario</span><br><br>
    <b>Observed:</b> infrastructure event + maritime observations<br>
    <b>Correlated:</b> time / location relationships<br>
    <b>Corroborated:</b> requires independent source classes<br>
    <b>Assessment:</b> cause not established<br>
    <b>Attribution:</b> not established</div>""",unsafe_allow_html=True)
with b:
    st.markdown("### INCIDENT GRAPH")
    st.code("""VESSEL ──observed at──> POSITION
   │                     │
   │                 near / time
   ▼                     ▼
PORT CALL          INFRASTRUCTURE
                         │
                    affected by
                         ▼
                      INCIDENT
                         │
                  corroborated by
                         ▼
                 INDEPENDENT SOURCE""",language=None)
    st.caption("The graph is the product logic; the map is the operational interface.")

st.divider()
st.caption("v2.0 prototype • Live AIS and EMODnet layers are source observations. Demo incident markers/feed are synthetic. Never infer causation, intent or attribution from proximity alone.")
