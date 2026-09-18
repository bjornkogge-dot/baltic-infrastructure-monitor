import streamlit as st
import pandas as pd
import requests, xml.etree.ElementTree as ET
import plotly.graph_objects as go
from datetime import datetime, timezone

st.set_page_config(page_title="Baltic Infrastructure Monitor v1.3", page_icon="◉", layout="wide")
st.markdown("""
<style>
.stApp{background:#061019;color:#eaf2f7}.block-container{padding-top:1rem;max-width:1580px}
[data-testid="stSidebar"]{background:#08151f}
[data-testid="stMetric"]{background:#0c1a25;border:1px solid #223746;border-radius:9px;padding:12px}
.panel{background:#0c1a25;border:1px solid #223746;border-radius:9px;padding:15px;margin-bottom:12px}
.kicker{color:#7f9aaa;font-size:.75rem;letter-spacing:.13em;font-weight:700}
.small{color:#8fa6b5;font-size:.82rem}.badge{font-size:.73rem;letter-spacing:.08em;font-weight:800;padding:.3rem .5rem;border:1px solid #456173;border-radius:5px;display:inline-block}
</style>""", unsafe_allow_html=True)

UA={"User-Agent":"BalticInfrastructureMonitor/1.3 open-data-demo"}
AIS_LOC="https://meri.digitraffic.fi/api/ais/v1/locations"
AIS_META="https://meri.digitraffic.fi/api/ais/v1/vessels"
PORT_CALLS="https://meri.digitraffic.fi/api/port-call/v1/port-calls"
PORTS="https://meri.digitraffic.fi/api/port-call/v1/ports"
SSE="https://meri.digitraffic.fi/api/sse/v1/measurements"
ATON="https://meri.digitraffic.fi/api/aton/v1/faults"
EMOD_WFS="https://ows.emodnet-humanactivities.eu/wfs"

def get_json(url, params=None, timeout=15):
    r=requests.get(url,params=params,headers=UA,timeout=timeout); r.raise_for_status(); return r.json()

@st.cache_data(ttl=60)
def fintraffic_ais():
    gj=get_json(AIS_LOC); meta=get_json(AIS_META)
    rows=[]
    for f in gj.get("features",[]):
        p=f.get("properties",{}); c=f.get("geometry",{}).get("coordinates",[None,None])
        rows.append({"mmsi":str(p.get("mmsi",f.get("mmsi",""))),"longitude":c[0],"latitude":c[1],
                     "speed_kn":p.get("sog"),"course_deg":p.get("cog"),"heading":p.get("heading"),
                     "timestamp":p.get("timestamp") or p.get("time")})
    pos=pd.DataFrame(rows)
    items=(meta.get("vessels") or meta.get("features") or meta.get("data") or []) if isinstance(meta,dict) else meta
    mr=[]
    for x in items:
        p=x.get("properties",x) if isinstance(x,dict) else {}
        mr.append({"mmsi":str(p.get("mmsi","")),"vessel_name":p.get("name") or "Unknown vessel",
                   "imo":p.get("imo"),"call_sign":p.get("callSign"),"destination":p.get("destination"),
                   "ship_type":p.get("type")})
    md=pd.DataFrame(mr)
    if len(md): pos=pos.merge(md,on="mmsi",how="left")
    if "vessel_name" not in pos: pos["vessel_name"]="Unknown vessel"
    pos["vessel_name"]=pos["vessel_name"].fillna("Unknown vessel")
    return pos.dropna(subset=["latitude","longitude"])

@st.cache_data(ttl=300)
def fintraffic_context():
    out={}
    for key,url in [("port_calls",PORT_CALLS),("ports",PORTS),("sea_state",SSE),("aton_faults",ATON)]:
        try:
            x=get_json(url,timeout=12)
            if isinstance(x,list): out[key]=len(x)
            elif isinstance(x,dict):
                seq=x.get("features") or x.get("portCalls") or x.get("data") or x.get("measurements") or x.get("faults")
                out[key]=len(seq) if isinstance(seq,list) else 1
            else: out[key]=0
        except Exception: out[key]=None
    return out

@st.cache_data(ttl=3600)
def emodnet_layer_names():
    r=requests.get(EMOD_WFS,params={"service":"WFS","request":"GetCapabilities","version":"2.0.0"},headers=UA,timeout=20)
    r.raise_for_status()
    root=ET.fromstring(r.content)
    names=[]
    for e in root.iter():
        if e.tag.endswith("FeatureType"):
            for ch in e:
                if ch.tag.endswith("Name") and ch.text: names.append(ch.text)
    return names

@st.cache_data(ttl=1800)
def emodnet_features(keyword, bbox="18,54,31,66", limit=1000):
    names=emodnet_layer_names()
    candidates=[n for n in names if keyword.lower() in n.lower()]
    if not candidates: return [], None
    layer=candidates[0]
    params={"service":"WFS","version":"2.0.0","request":"GetFeature","typeNames":layer,
            "bbox":bbox,"outputFormat":"application/json","count":limit}
    try: return get_json(EMOD_WFS,params=params,timeout=25).get("features",[]),layer
    except Exception: return [],layer

def flatten_geom(feature):
    g=feature.get("geometry") or {}; typ=g.get("type"); c=g.get("coordinates")
    pts=[]
    if typ=="Point": pts=[c]
    elif typ=="LineString": pts=c
    elif typ=="MultiLineString":
        for line in c: pts += line + [[None,None]]
    return pts

st.markdown('<div class="kicker">MULTI-SOURCE OPEN INTELLIGENCE / MARITIME DOMAIN</div>',unsafe_allow_html=True)
st.markdown("# BALTIC INFRASTRUCTURE MONITOR")
st.caption("v1.3 • Data Fusion Prototype • AIS + Infrastructure + Port/Sea-State Context")

with st.sidebar:
    st.markdown("### DATA FUSION")
    show_ais=st.toggle("Fintraffic live AIS",True)
    show_cables=st.toggle("EMODnet cables",True)
    show_pipes=st.toggle("EMODnet pipelines",False)
    show_demo=st.toggle("Synthetic fallback layer",False)
    st.divider()
    max_vessels=st.slider("AIS vessel limit",100,3000,1200,100)
    st.caption("EMODnet layers are queried through its official WFS service.")
    st.divider()
    st.markdown("### HIGH NORTH CONNECTOR")
    st.info("BarentsWatch adapter is staged for v1.3 but requires a free API client/token. Keep credentials in Streamlit Secrets — never in GitHub.")

if st.button("Refresh open data"):
    st.cache_data.clear()

errors=[]
try: ais=fintraffic_ais().head(max_vessels) if show_ais else pd.DataFrame()
except Exception as e: ais=pd.DataFrame(); errors.append("Fintraffic AIS")
ctx=fintraffic_context()
try: cables,cable_layer=emodnet_features("cable") if show_cables else ([],None)
except Exception: cables=[]; cable_layer=None; errors.append("EMODnet cables")
try: pipes,pipe_layer=emodnet_features("pipeline") if show_pipes else ([],None)
except Exception: pipes=[]; pipe_layer=None; errors.append("EMODnet pipelines")

m1,m2,m3,m4,m5=st.columns(5)
m1.metric("AIS OBSERVATIONS",f"{len(ais):,}")
m2.metric("CABLE FEATURES",f"{len(cables):,}")
m3.metric("PIPELINE FEATURES",f"{len(pipes):,}")
m4.metric("PORT CALL RECORDS",ctx.get("port_calls") if ctx.get("port_calls") is not None else "N/A")
m5.metric("ATON FAULTS",ctx.get("aton_faults") if ctx.get("aton_faults") is not None else "N/A")

if errors: st.warning("Some open-data connectors did not respond: "+", ".join(errors)+". Other layers remain available.")
else: st.success("MULTI-SOURCE DATA FUSION ACTIVE — independent open-data layers are being loaded from official services.")

mapcol,side=st.columns([2.45,1],gap="large")
with mapcol:
    st.markdown("### COMMON OPERATING PICTURE")
    fig=go.Figure()
    if len(ais):
        fig.add_trace(go.Scattermap(lat=ais.latitude,lon=ais.longitude,mode="markers",
            marker={"size":6},name="Fintraffic AIS",
            text=ais.apply(lambda r:f"<b>{r.get('vessel_name','Unknown')}</b><br>MMSI {r.get('mmsi','')}<br>SOG {r.get('speed_kn','?')} kn<br>COG {r.get('course_deg','?')}°",axis=1),
            hovertemplate="%{text}<extra></extra>"))
    for features,label in [(cables,"EMODnet cable"),(pipes,"EMODnet pipeline")]:
        for i,f in enumerate(features[:300]):
            pts=flatten_geom(f)
            if pts:
                lons=[p[0] for p in pts]; lats=[p[1] for p in pts]
                fig.add_trace(go.Scattermap(lat=lats,lon=lons,mode="lines",line={"width":3},
                    name=label if i==0 else label,showlegend=(i==0),
                    hovertemplate=f"<b>{label}</b><extra></extra>"))
    if show_demo:
        infra=pd.read_csv("infrastructure.csv")
        for _,r in infra.iterrows():
            fig.add_trace(go.Scattermap(lat=[r.start_lat,r.end_lat],lon=[r.start_lon,r.end_lon],
                mode="lines",line={"width":4},name="SYNTHETIC: "+r["name"]))
    fig.update_layout(map={"style":"carto-darkmatter","center":{"lat":59.7,"lon":24.5},"zoom":4.7},
        height=720,margin={"l":0,"r":0,"t":0,"b":0},paper_bgcolor="#061019",font={"color":"#dce8ef"})
    st.plotly_chart(fig,use_container_width=True)
    st.caption("Layers retain their source identity. Proximity alone does not establish causation, intent, wrongdoing or attribution.")

with side:
    st.markdown("### SOURCE FUSION")
    def status(v): return "AVAILABLE" if v is not None else "UNAVAILABLE"
    st.markdown(f"""<div class="panel">
    <b>Fintraffic AIS</b><br><span class="small">{len(ais):,} current observations</span><br><br>
    <b>EMODnet cables</b><br><span class="small">{len(cables):,} features • {cable_layer or 'layer not resolved'}</span><br><br>
    <b>EMODnet pipelines</b><br><span class="small">{len(pipes):,} features • {pipe_layer or 'not enabled / unresolved'}</span><br><br>
    <b>Fintraffic Portnet</b><br><span class="small">{status(ctx.get('port_calls'))}</span><br><br>
    <b>Sea-state estimates</b><br><span class="small">{status(ctx.get('sea_state'))}</span><br><br>
    <b>AtoN faults</b><br><span class="small">{status(ctx.get('aton_faults'))}</span>
    </div>""",unsafe_allow_html=True)
    st.markdown("### FUSION LOGIC")
    st.markdown("""<div class="panel">
    <b>OBSERVED</b><br><span class="small">Source-specific raw observation.</span><br><br>
    <b>CORRELATED</b><br><span class="small">Time/location/entity relationship detected.</span><br><br>
    <b>CORROBORATED</b><br><span class="small">Supported by independent source classes.</span><br><br>
    <b>ASSESSED</b><br><span class="small">Human/analytic interpretation, kept separate from facts.</span>
    </div>""",unsafe_allow_html=True)
    st.markdown("### HIGH NORTH")
    st.write("BarentsWatch live + historic AIS is the next authenticated connector. Its credentials should be stored as deployment secrets.")

st.divider()
st.markdown("### INCIDENT GRAPH — v1.3 FOUNDATION")
st.code("VESSEL → observed at → POSITION\nPOSITION → near → INFRASTRUCTURE\nVESSEL → planned/recorded → PORT CALL\nPOSITION → contextualised by → SEA STATE\nINFRASTRUCTURE → sourced from → EMODNET\nOBSERVATION → corroborated by → INDEPENDENT SOURCE",language=None)
st.caption("v1.3 is a prototype, not a navigation, safety, enforcement or attribution system. Open-source data can be incomplete, delayed or erroneous.")
