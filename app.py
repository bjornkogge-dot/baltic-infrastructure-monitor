
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from math import radians, sin, cos, asin, sqrt

st.set_page_config(page_title="Baltic Infrastructure Monitor", layout="wide")
st.title("Baltic Infrastructure Monitor — Prototype v0.1")
st.caption("Synthetic demonstration data only. No real vessel behaviour or attribution is represented.")

ais=pd.read_csv("ais_demo.csv")
infra=pd.read_csv("infrastructure.csv")
inc=pd.read_csv("incidents.csv").iloc[0]

def hav(lat1,lon1,lat2,lon2):
    R=6371
    dlat=radians(lat2-lat1); dlon=radians(lon2-lon1)
    a=sin(dlat/2)**2+cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return 2*R*asin(sqrt(a))

ais["distance_to_incident_km"]=ais.apply(lambda r:hav(r.latitude,r.longitude,inc.latitude,inc.longitude),axis=1)
summary=ais.groupby("vessel_name").agg(
    closest_approach_km=("distance_to_incident_km","min"),
    min_speed_kn=("speed_kn","min"),
    max_speed_kn=("speed_kn","max"),
    max_course_deg=("course_deg","max"),
    min_course_deg=("course_deg","min")
).reset_index()
summary["course_change_deg"]=summary.max_course_deg-summary.min_course_deg
summary["review_flag"]=(summary.closest_approach_km<5)&((summary.min_speed_kn<4)|(summary.course_change_deg>30))

left,right=st.columns([2.2,1])
with left:
    fig=go.Figure()
    c=infra.iloc[0]
    fig.add_trace(go.Scattermap(lat=[c.lat_start,c.lat_end],lon=[c.lon_start,c.lon_end],
                                mode="lines",line={"width":5},name=c["name"]))
    for vessel,g in ais.groupby("vessel_name"):
        fig.add_trace(go.Scattermap(lat=g.latitude,lon=g.longitude,mode="lines+markers",
                                    marker={"size":5},name=vessel,
                                    text=[f"{vessel}<br>{t}<br>{s} kn" for t,s in zip(g.timestamp,g.speed_kn)]))
    fig.add_trace(go.Scattermap(lat=[inc.latitude],lon=[inc.longitude],mode="markers",
                                marker={"size":16},name="Incident"))
    fig.update_layout(map={"style":"open-street-map","center":{"lat":59.84,"lon":24.9},"zoom":8},
                      height=610,margin={"l":0,"r":0,"t":0,"b":0})
    st.plotly_chart(fig,use_container_width=True)

with right:
    st.subheader("Incident")
    st.write(f"**{inc['incident']}**")
    st.write(f"Time: {inc['timestamp']}")
    st.write(f"Infrastructure: {inc['infrastructure']}")
    vessel=st.selectbox("Inspect vessel",summary.vessel_name.tolist())
    s=summary[summary.vessel_name==vessel].iloc[0]
    st.metric("Closest approach",f"{s.closest_approach_km:.2f} km")
    st.metric("Minimum speed",f"{s.min_speed_kn:.1f} kn")
    st.metric("Course change",f"{s.course_change_deg:.0f}°")
    if s.review_flag:
        st.warning("REQUIRES REVIEW — proximity plus predefined movement indicator.")
    else:
        st.success("No review rule triggered.")
    st.caption("A review flag is an analytic indicator, not evidence of wrongdoing.")

st.subheader("Vessel observations")
st.dataframe(summary[["vessel_name","closest_approach_km","min_speed_kn","max_speed_kn","course_change_deg","review_flag"]],
             use_container_width=True,hide_index=True)
