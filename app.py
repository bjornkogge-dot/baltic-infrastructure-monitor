import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from math import radians, sin, cos, asin, sqrt
from datetime import timedelta

st.set_page_config(page_title="Baltic Infrastructure Monitor", page_icon="◉", layout="wide")

st.markdown("""
<style>
.stApp{background:#061019;color:#eaf2f7}.block-container{padding-top:1rem;max-width:1550px}
[data-testid="stSidebar"]{background:#08151f}
[data-testid="stMetric"]{background:#0c1a25;border:1px solid #223746;border-radius:9px;padding:12px}
.panel{background:#0c1a25;border:1px solid #223746;border-radius:9px;padding:15px;margin:0 0 12px 0}
.kicker{color:#7f9aaa;font-size:.75rem;letter-spacing:.13em;font-weight:700}
.small{color:#8fa6b5;font-size:.82rem}
.badge{font-size:.73rem;letter-spacing:.08em;font-weight:800;padding:.3rem .5rem;border:1px solid #456173;border-radius:5px;display:inline-block}
hr{border-color:#1d3341}
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load():
    ais = pd.read_csv("ais_demo.csv")
    infra = pd.read_csv("infrastructure.csv")
    inc = pd.read_csv("incidents.csv")
    ais["timestamp"] = pd.to_datetime(ais["timestamp"], utc=True)
    inc["timestamp"] = pd.to_datetime(inc["timestamp"], utc=True)
    return ais, infra, inc

ais, infra, incidents = load()
inc = incidents.iloc[0]
incident_time = inc["timestamp"]

def hav(lat1, lon1, lat2, lon2):
    R=6371
    dlat=radians(lat2-lat1); dlon=radians(lon2-lon1)
    a=sin(dlat/2)**2+cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return 2*R*asin(sqrt(a))

ais["distance_to_incident_km"] = ais.apply(
    lambda r: hav(r.latitude, r.longitude, inc.latitude, inc.longitude), axis=1
)
summary = ais.groupby(["vessel_name","mmsi","imo"], as_index=False).agg(
    closest_approach_km=("distance_to_incident_km","min"),
    min_speed_kn=("speed_kn","min"),
    max_speed_kn=("speed_kn","max"),
    max_course_deg=("course_deg","max"),
    min_course_deg=("course_deg","min"),
    first_seen=("timestamp","min"),
    last_seen=("timestamp","max")
)
summary["course_change_deg"]=(summary.max_course_deg-summary.min_course_deg).abs()
summary["proximity_indicator"]=summary.closest_approach_km < 5
summary["speed_indicator"]=summary.min_speed_kn < 4
summary["course_indicator"]=summary.course_change_deg > 30
summary["review_flag"]=summary.proximity_indicator & (summary.speed_indicator | summary.course_indicator)
summary["status"]=summary.review_flag.map({True:"REVIEW",False:"ROUTINE"})

st.markdown('<div class="kicker">MARITIME SITUATIONAL AWARENESS / CRITICAL INFRASTRUCTURE</div>', unsafe_allow_html=True)
st.markdown("# BALTIC INFRASTRUCTURE MONITOR")
st.caption("Prototype v1.0 • Detect → Verify → Contextualise → Assess → Alert → Decide")
st.warning("DEMONSTRATION ONLY — vessel tracks, identifiers, infrastructure and incident details are synthetic. Analytic indicators are not evidence of wrongdoing or attribution.")

with st.sidebar:
    st.markdown("### OPERATIONS")
    mode = st.radio("Workspace", ["Live picture","Incident investigation","Intelligence brief"], label_visibility="collapsed")
    st.divider()
    st.markdown("**Time window**")
    window = st.select_slider("Window", options=["Before","Incident","After","Full"], value="Full", label_visibility="collapsed")
    show_zone = st.toggle("5 km review zone", True)
    show_labels = st.toggle("Vessel labels", True)
    st.divider()
    st.markdown("**Layers**")
    st.checkbox("AIS vessel tracks", True, disabled=True)
    st.checkbox("Critical infrastructure", True, disabled=True)
    st.checkbox("Incident markers", True, disabled=True)
    st.checkbox("Source reporting", True, disabled=True)
    st.caption("v1.0 demo uses local synthetic data. API connectors are the next integration layer.")

if window=="Before":
    view=ais[ais.timestamp < incident_time]
elif window=="Incident":
    view=ais[(ais.timestamp >= incident_time-timedelta(minutes=30)) & (ais.timestamp <= incident_time+timedelta(minutes=30))]
elif window=="After":
    view=ais[ais.timestamp > incident_time]
else:
    view=ais

m1,m2,m3,m4,m5=st.columns(5)
m1.metric("INCIDENT STATUS","ACTIVE REVIEW")
m2.metric("TRACKED VESSELS",len(summary))
m3.metric("REVIEW INDICATORS",int(summary.review_flag.sum()))
m4.metric("CRITICAL ASSETS",len(infra))
m5.metric("CONFIDENCE","DEMO")

if mode == "Live picture":
    mapcol, right = st.columns([2.25,1], gap="large")
    with mapcol:
        st.markdown("### COMMON OPERATING PICTURE")
        fig=go.Figure()

        for _, r in infra.iterrows():
            if {"start_lat","start_lon","end_lat","end_lon"}.issubset(infra.columns):
                fig.add_trace(go.Scattermap(
                    lat=[r.start_lat,r.end_lat], lon=[r.start_lon,r.end_lon],
                    mode="lines", line={"width":5}, name=r["name"],
                    hovertemplate=f"<b>{r['name']}</b><br>{r['type']}<extra></extra>"
                ))

        for vessel, g in view.groupby("vessel_name"):
            s=summary[summary.vessel_name==vessel].iloc[0]
            fig.add_trace(go.Scattermap(
                lat=g.latitude, lon=g.longitude, mode="lines+markers",
                marker={"size":7}, line={"width":3},
                name=vessel + (" • REVIEW" if s.review_flag else ""),
                text=[f"{vessel}<br>{t}<br>{sp:.1f} kn<br>{d:.1f} km from incident"
                      for t,sp,d in zip(g.timestamp.dt.strftime("%H:%M UTC"),g.speed_kn,g.distance_to_incident_km)],
                hovertemplate="%{text}<extra></extra>"
            ))
            if show_labels and len(g):
                last=g.iloc[-1]
                fig.add_trace(go.Scattermap(
                    lat=[last.latitude],lon=[last.longitude],mode="text",
                    text=[vessel],textposition="top right",showlegend=False,hoverinfo="skip"
                ))

        fig.add_trace(go.Scattermap(
            lat=[inc.latitude],lon=[inc.longitude],mode="markers+text",
            marker={"size":18},text=["INCIDENT"],textposition="top center",
            name="Incident",hovertemplate=f"<b>{inc['incident']}</b><br>{incident_time.strftime('%Y-%m-%d %H:%M UTC')}<extra></extra>"
        ))

        if show_zone:
            # visual approximation only; explicitly labelled in UI
            fig.add_trace(go.Scattermap(
                lat=[inc.latitude],lon=[inc.longitude],mode="markers",
                marker={"size":70,"opacity":0.13},name="5 km review zone",hoverinfo="skip"
            ))

        fig.update_layout(
            map={"style":"carto-darkmatter","center":{"lat":inc.latitude,"lon":inc.longitude},"zoom":7.1},
            height=650,margin={"l":0,"r":0,"t":0,"b":0},
            legend={"orientation":"h","y":0.01,"x":0.01},
            paper_bgcolor="#061019",font={"color":"#dce8ef"}
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Review zone is a visual analytic aid. It does not represent a legal, security, or attribution boundary.")

    with right:
        st.markdown("### INCIDENT ASSESSMENT")
        st.markdown(f"""<div class="panel"><span class="badge">REQUIRES ANALYST REVIEW</span><br><br>
        <b>{inc['incident']}</b><br><span class="small">{incident_time.strftime('%Y-%m-%d %H:%M UTC')}<br>{inc['infrastructure']}</span>
        <hr><b>Assessment</b><br>Multiple observable maritime indicators occur within the synthetic incident window. Cause and attribution are not established.</div>""", unsafe_allow_html=True)

        vessel=st.selectbox("Inspect vessel", summary.vessel_name.tolist())
        s=summary[summary.vessel_name==vessel].iloc[0]
        st.markdown(f"""<div class="panel"><div class="kicker">VESSEL PROFILE</div><b>{vessel}</b><br>
        <span class="small">MMSI {s.mmsi} • IMO {s.imo}</span><hr>
        Closest approach <b>{s.closest_approach_km:.1f} km</b><br>
        Speed range <b>{s.min_speed_kn:.1f}–{s.max_speed_kn:.1f} kn</b><br>
        Course delta <b>{s.course_change_deg:.0f}°</b><br><br>
        <span class="badge">{s.status}</span></div>""", unsafe_allow_html=True)

        indicators=[]
        if s.proximity_indicator: indicators.append("Infrastructure proximity")
        if s.speed_indicator: indicators.append("Low-speed movement")
        if s.course_indicator: indicators.append("Course variation")
        st.markdown("**Triggered indicators**")
        st.write(" • ".join(indicators) if indicators else "No predefined review indicators.")

        st.markdown("### SOURCE FUSION")
        st.markdown("""<div class="panel">
        <b>✓ AIS observations</b><br><span class="small">Synthetic track data • available</span><br><br>
        <b>✓ Infrastructure layer</b><br><span class="small">Synthetic asset geometry • available</span><br><br>
        <b>○ Official reporting</b><br><span class="small">Connector placeholder</span><br><br>
        <b>○ News / OSINT</b><br><span class="small">Connector placeholder</span>
        </div>""", unsafe_allow_html=True)

elif mode == "Incident investigation":
    st.markdown("### INCIDENT INVESTIGATION")
    left,right=st.columns([1.25,1],gap="large")
    with left:
        st.markdown("#### Vessel review queue")
        display=summary[["vessel_name","closest_approach_km","min_speed_kn","course_change_deg","status"]].copy()
        display.columns=["Vessel","Closest approach (km)","Min speed (kn)","Course delta (°)","Status"]
        st.dataframe(display.sort_values(["Status","Closest approach (km)"],ascending=[False,True]),use_container_width=True,hide_index=True)

        st.markdown("#### Incident timeline")
        timeline=pd.DataFrame([
            {"Time":(incident_time-timedelta(minutes=60)).strftime("%H:%M"),"Event":"Pre-incident monitoring window opens","Verification":"System"},
            {"Time":(incident_time-timedelta(minutes=20)).strftime("%H:%M"),"Event":"Vessel proximity indicators evaluated","Verification":"System"},
            {"Time":incident_time.strftime("%H:%M"),"Event":"Synthetic infrastructure incident registered","Verification":"Demo"},
            {"Time":(incident_time+timedelta(minutes=25)).strftime("%H:%M"),"Event":"Movement changes correlated with incident window","Verification":"System"},
            {"Time":(incident_time+timedelta(minutes=60)).strftime("%H:%M"),"Event":"Initial intelligence picture available","Verification":"Analyst review required"},
        ])
        st.dataframe(timeline,use_container_width=True,hide_index=True)
    with right:
        st.markdown("#### Analytic logic")
        st.markdown("""<div class="panel"><b>1. Detect</b><br><span class="small">Register infrastructure event and nearby observations.</span><br><br>
        <b>2. Correlate</b><br><span class="small">Link vessels, time, location and infrastructure.</span><br><br>
        <b>3. Verify</b><br><span class="small">Separate confirmed, unconfirmed and conflicting information.</span><br><br>
        <b>4. Assess</b><br><span class="small">Surface indicators for human review without inferring intent.</span><br><br>
        <b>5. Brief</b><br><span class="small">Produce a sourced initial situation picture.</span></div>""", unsafe_allow_html=True)
        st.markdown("#### Data model")
        st.code("VESSEL → observed near → INFRASTRUCTURE\nVESSEL → during → INCIDENT WINDOW\nINCIDENT → reported by → SOURCE\nINDICATOR → requires → ANALYST REVIEW", language=None)

else:
    st.markdown("### INITIAL INTELLIGENCE BRIEF")
    flagged=summary[summary.review_flag]
    closest=summary.sort_values("closest_approach_km").iloc[0]
    brief=f"""SITUATION
A synthetic critical-infrastructure incident is registered at {incident_time.strftime('%Y-%m-%d %H:%M UTC')}. The platform correlates maritime observations with the incident location and time window.

OBSERVATIONS
{len(summary)} vessels are tracked in the demonstration dataset. {int(summary.review_flag.sum())} meet the predefined review rule. The closest synthetic approach is {closest.closest_approach_km:.1f} km by {closest.vessel_name}.

ASSESSMENT
The available synthetic observations justify analyst review where proximity coincides with low-speed movement or material course variation. These indicators do not establish causation, intent, wrongdoing, or attribution.

CONFIDENCE
DEMO / NOT AN OPERATIONAL ASSESSMENT.

INFORMATION GAPS
Official reporting, real AIS feeds, weather, infrastructure telemetry, satellite data and independent OSINT sources are not connected in this prototype.

RECOMMENDED MONITORING
Continue multi-source collection; verify incident facts independently; preserve the vessel timeline; compare movement with weather, navigational constraints and normal traffic patterns; update the assessment as corroborated information arrives."""
    st.text_area("Generated brief", brief, height=430)
    st.download_button("Download brief (.txt)", brief, file_name="initial_intelligence_brief.txt", mime="text/plain")
    st.caption("The brief is generated from synthetic local demo data and is intended to demonstrate workflow and product structure only.")

st.divider()
st.caption("Baltic Infrastructure Monitor v1.0 • Synthetic demonstration environment • No operational, legal or attribution conclusions.")
