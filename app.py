import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from math import radians, sin, cos, asin, sqrt
from datetime import datetime, timezone

st.set_page_config(page_title="Baltic Infrastructure Monitor v1.2", page_icon="◉", layout="wide")
st.markdown("""
<style>
.stApp{background:#061019;color:#eaf2f7}.block-container{padding-top:1rem;max-width:1550px}
[data-testid="stSidebar"]{background:#08151f}
[data-testid="stMetric"]{background:#0c1a25;border:1px solid #223746;border-radius:9px;padding:12px}
.panel{background:#0c1a25;border:1px solid #223746;border-radius:9px;padding:15px;margin-bottom:12px}
.kicker{color:#7f9aaa;font-size:.75rem;letter-spacing:.13em;font-weight:700}
.small{color:#8fa6b5;font-size:.82rem}.badge{font-size:.73rem;letter-spacing:.08em;font-weight:800;padding:.3rem .5rem;border:1px solid #456173;border-radius:5px;display:inline-block}
</style>""", unsafe_allow_html=True)

DIGI_LOC="https://meri.digitraffic.fi/api/ais/v1/locations"
DIGI_VES="https://meri.digitraffic.fi/api/ais/v1/vessels"
HEADERS={"User-Agent":"BalticInfrastructureMonitor/1.2 demo"}

def hav(lat1,lon1,lat2,lon2):
    R=6371; dlat=radians(lat2-lat1); dlon=radians(lon2-lon1)
    a=sin(dlat/2)**2+cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return 2*R*asin(sqrt(a))

@st.cache_data(ttl=60)
def digitraffic_live():
    loc=requests.get(DIGI_LOC,headers=HEADERS,timeout=12); loc.raise_for_status()
    ves=requests.get(DIGI_VES,headers=HEADERS,timeout=12); ves.raise_for_status()
    gj=loc.json(); meta=ves.json()
    rows=[]
    for f in gj.get("features",[]):
        p=f.get("properties",{}); c=f.get("geometry",{}).get("coordinates",[None,None])
        mmsi=str(p.get("mmsi",f.get("mmsi","")))
        rows.append({"mmsi":mmsi,"longitude":c[0],"latitude":c[1],
                     "speed_kn":p.get("sog"),"course_deg":p.get("cog"),
                     "heading":p.get("heading"),"timestamp":p.get("timestamp") or p.get("time")})
    pos=pd.DataFrame(rows)
    # API metadata may be a list or a wrapper object depending on version.
    if isinstance(meta,dict):
        items=meta.get("vessels") or meta.get("features") or meta.get("data") or []
    else: items=meta
    mr=[]
    for x in items:
        p=x.get("properties",x) if isinstance(x,dict) else {}
        mr.append({"mmsi":str(p.get("mmsi","")),"vessel_name":p.get("name") or "Unknown vessel",
                   "imo":p.get("imo"),"call_sign":p.get("callSign"),"destination":p.get("destination"),
                   "ship_type":p.get("type")})
    md=pd.DataFrame(mr)
    if len(md) and "mmsi" in md: pos=pos.merge(md,on="mmsi",how="left")
    if "vessel_name" not in pos: pos["vessel_name"]="Unknown vessel"
    pos["vessel_name"]=pos["vessel_name"].fillna("Unknown vessel")
    pos=pos.dropna(subset=["latitude","longitude"])
    return pos

def synthetic():
    d=pd.read_csv("ais_demo.csv")
    return d

st.markdown('<div class="kicker">OPEN-SOURCE MARITIME SITUATIONAL AWARENESS</div>',unsafe_allow_html=True)
st.markdown("# BALTIC INFRASTRUCTURE MONITOR")
st.caption("v1.2 • Open AIS integration • Finland / Baltic Sea")

with st.sidebar:
    st.markdown("### DATA SOURCE")
    source=st.radio("AIS feed",["Fintraffic Digitraffic — LIVE","Synthetic demo"],index=0)
    st.caption("Live mode uses Fintraffic's open Finnish marine AIS API. Coverage is source-dependent.")
    st.divider()
    refresh=st.button("Refresh live AIS",use_container_width=True)
    st.markdown("### FILTERS")
    max_vessels=st.slider("Maximum vessels",100,3000,1000,100)
    speed_filter=st.slider("Minimum SOG (kn)",0.0,25.0,0.0,0.5)
    show_names=st.toggle("Show vessel names",False)
    st.divider()
    st.markdown("### ANALYTIC LAYERS")
    show_infra=st.toggle("Demo infrastructure",True)
    st.caption("Infrastructure layer remains synthetic in v1.2 and is visually separated from live AIS.")

if refresh: st.cache_data.clear()

live=False; error=None
if source.startswith("Fintraffic"):
    try:
        data=digitraffic_live(); live=True
    except Exception as e:
        error=str(e); data=synthetic()
else: data=synthetic()

if live:
    st.success("LIVE OPEN DATA — Fintraffic Digitraffic AIS. Vessel positions are real source observations; no intent or attribution is inferred.")
else:
    if error: st.error("Live AIS could not be reached from this deployment. Showing synthetic fallback data instead.")
    else: st.info("Synthetic demo mode.")
    if error: st.caption("Connector error: "+error[:220])

infra=pd.read_csv("infrastructure.csv")
data["speed_kn"]=pd.to_numeric(data.get("speed_kn"),errors="coerce")
data=data[data["speed_kn"].fillna(0)>=speed_filter].head(max_vessels)

m1,m2,m3,m4=st.columns(4)
m1.metric("AIS OBSERVATIONS",f"{len(data):,}")
m2.metric("DATA MODE","LIVE" if live else "SYNTHETIC")
m3.metric("SOURCE","FINTRAFFIC" if live else "LOCAL DEMO")
m4.metric("REFRESH","60 SEC CACHE" if live else "STATIC")

mapcol,side=st.columns([2.4,1],gap="large")
with mapcol:
    st.markdown("### COMMON OPERATING PICTURE")
    fig=go.Figure()
    if live:
        text=[]
        for _,r in data.iterrows():
            nm=r.get("vessel_name","Unknown vessel")
            text.append(f"<b>{nm}</b><br>MMSI {r.get('mmsi','')}<br>SOG {r.get('speed_kn','?')} kn<br>COG {r.get('course_deg','?')}°")
        fig.add_trace(go.Scattermap(lat=data.latitude,lon=data.longitude,mode="markers+text" if show_names else "markers",
            text=data.vessel_name if show_names else None,customdata=text,marker={"size":7},
            hovertemplate="%{customdata}<extra></extra>",name="Live AIS"))
    else:
        for vessel,g in data.groupby("vessel_name"):
            fig.add_trace(go.Scattermap(lat=g.latitude,lon=g.longitude,mode="lines+markers",name=vessel,
                marker={"size":7},hovertemplate=vessel+"<extra></extra>"))
    if show_infra and {"start_lat","start_lon","end_lat","end_lon"}.issubset(infra.columns):
        for _,r in infra.iterrows():
            fig.add_trace(go.Scattermap(lat=[r.start_lat,r.end_lat],lon=[r.start_lon,r.end_lon],
                mode="lines",line={"width":4},name="SYNTHETIC: "+r["name"],
                hovertemplate="<b>SYNTHETIC INFRASTRUCTURE</b><br>"+r["name"]+"<extra></extra>"))
    fig.update_layout(map={"style":"carto-darkmatter","center":{"lat":60.0,"lon":24.5},"zoom":5.3},
        height=690,margin={"l":0,"r":0,"t":0,"b":0},paper_bgcolor="#061019",font={"color":"#dce8ef"})
    st.plotly_chart(fig,use_container_width=True)
    st.caption("Live AIS reflects what the open source exposes at retrieval time. AIS can be incomplete, delayed, erroneous or absent and should be corroborated for operational use.")

with side:
    st.markdown("### SOURCE STATUS")
    st.markdown(f"""<div class="panel"><span class="badge">{'LIVE' if live else 'FALLBACK'}</span><br><br>
    <b>{'Fintraffic Digitraffic' if live else 'Synthetic local dataset'}</b><br>
    <span class="small">{'Open Finnish marine traffic AIS API' if live else 'Demonstration data only'}</span>
    <hr><b>Observations loaded</b><br>{len(data):,}</div>""",unsafe_allow_html=True)
    st.markdown("### VESSEL INSPECTOR")
    if len(data):
        opts=data.drop_duplicates("mmsi").copy()
        opts["label"]=opts.apply(lambda r:f"{r.get('vessel_name','Unknown')} · {r.get('mmsi','')}",axis=1)
        chosen=st.selectbox("Vessel",opts["label"].tolist())
        r=opts[opts.label==chosen].iloc[0]
        st.markdown(f"""<div class="panel"><b>{r.get('vessel_name','Unknown vessel')}</b><br>
        <span class="small">MMSI {r.get('mmsi','—')} • IMO {r.get('imo','—')}</span><hr>
        SOG <b>{r.get('speed_kn','—')} kn</b><br>COG <b>{r.get('course_deg','—')}°</b><br>
        Destination <b>{r.get('destination','—')}</b></div>""",unsafe_allow_html=True)
    st.markdown("### VERIFICATION")
    st.markdown("""<div class="panel"><b>Observation</b><br><span class="small">AIS position / metadata from selected source.</span><br><br>
    <b>Assessment</b><br><span class="small">Not automatically inferred from proximity or movement.</span><br><br>
    <b>Attribution</b><br><span class="small">Not established by AIS alone.</span></div>""",unsafe_allow_html=True)

st.divider()
st.markdown("### v1.2 DATA ROADMAP")
st.write("**Connected:** Fintraffic Digitraffic open AIS.  **Next connectors:** Norwegian Coastal Administration / BarentsWatch AIS, open weather and sea-state feeds, port calls, navigation-aid faults, and sourced critical-infrastructure layers.")
st.caption("Prototype v1.2 • Open-source data integration • Do not use as a sole source for safety, navigation, enforcement, or attribution decisions.")
