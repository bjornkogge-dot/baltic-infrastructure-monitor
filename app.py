import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from math import radians, sin, cos, asin, sqrt

st.set_page_config(page_title='Baltic Infrastructure Monitor', page_icon='◉', layout='wide')
st.markdown('''<style>
.stApp{background:#071018;color:#e8f0f5}.block-container{padding-top:1.2rem;max-width:1500px}
[data-testid="stMetric"]{background:#0d1923;border:1px solid #243543;border-radius:8px;padding:12px}
[data-testid="stSidebar"]{background:#09141d}.status{font-size:.78rem;letter-spacing:.08em;font-weight:700;padding:.35rem .55rem;border:1px solid #3b5668;border-radius:5px;display:inline-block}
.small{color:#8ea3b2;font-size:.82rem}.panel{background:#0d1923;border:1px solid #243543;border-radius:8px;padding:14px;margin-bottom:10px}
</style>''', unsafe_allow_html=True)

ais=pd.read_csv('ais_demo.csv'); infra=pd.read_csv('infrastructure.csv'); inc=pd.read_csv('incidents.csv').iloc[0]
ais['timestamp']=pd.to_datetime(ais['timestamp']); incident_time=pd.to_datetime(inc['timestamp'])

def hav(lat1,lon1,lat2,lon2):
    R=6371; dlat=radians(lat2-lat1); dlon=radians(lon2-lon1)
    a=sin(dlat/2)**2+cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return 2*R*asin(sqrt(a))

ais['distance_to_incident_km']=ais.apply(lambda r:hav(r.latitude,r.longitude,inc.latitude,inc.longitude),axis=1)
summary=ais.groupby('vessel_name').agg(closest_approach_km=('distance_to_incident_km','min'),min_speed_kn=('speed_kn','min'),max_speed_kn=('speed_kn','max'),max_course_deg=('course_deg','max'),min_course_deg=('course_deg','min')).reset_index()
summary['course_change_deg']=(summary.max_course_deg-summary.min_course_deg).abs()
summary['review_flag']=(summary.closest_approach_km<5)&((summary.min_speed_kn<4)|(summary.course_change_deg>30))
summary['status']=summary.review_flag.map({True:'REVIEW',False:'ROUTINE'})

st.markdown('## BALTIC INFRASTRUCTURE MONITOR')
st.markdown('<span class="small">Maritime situational awareness • Critical infrastructure • Prototype v0.2</span>',unsafe_allow_html=True)
st.warning('DEMONSTRATION ONLY — all vessel tracks, identifiers, infrastructure and incident details in this prototype are synthetic. Indicators are not evidence of wrongdoing.')

m1,m2,m3,m4=st.columns(4)
m1.metric('INCIDENT STATUS','ACTIVE REVIEW'); m2.metric('TRACKED VESSELS',len(summary)); m3.metric('REVIEW INDICATORS',int(summary.review_flag.sum())); m4.metric('DATA CONFIDENCE','DEMO')

mapcol, intel=st.columns([2.35,1],gap='large')
with intel:
    st.markdown('### INCIDENT ASSESSMENT')
    st.markdown(f'''<div class="panel"><div class="status">REQUIRES ANALYST REVIEW</div><br><br><b>{inc['incident']}</b><br><span class="small">{inc['timestamp']} UTC<br>{inc['infrastructure']}</span></div>''',unsafe_allow_html=True)
    vessel=st.selectbox('Inspect vessel',summary.vessel_name.tolist())
    s=summary[summary.vessel_name==vessel].iloc[0]
    a,b=st.columns(2); a.metric('Closest approach',f'{s.closest_approach_km:.2f} km'); b.metric('Min speed',f'{s.min_speed_kn:.1f} kn')
    a,b=st.columns(2); a.metric('Course change',f'{s.course_change_deg:.0f}°'); b.metric('Indicator',s.status)
    st.markdown('**Assessment**')
    if s.review_flag: st.warning('Observable proximity plus a predefined movement indicator warrants analyst review.')
    else: st.info('No predefined review rule triggered for this synthetic track.')
    st.markdown('**Attribution:** NOT ESTABLISHED  \n**Analytic confidence:** MEDIUM (demo logic)')
    st.caption('The system surfaces indicators and context. Human analysts determine significance.')

with mapcol:
    st.markdown('### OPERATIONAL PICTURE')
    phase=st.radio('Timeline view',['Before','Incident','After','Full track'],horizontal=True,index=3)
    if phase=='Before': view=ais[ais.timestamp<incident_time]
    elif phase=='Incident': view=ais[(ais.timestamp>=incident_time-pd.Timedelta('30min'))&(ais.timestamp<=incident_time+pd.Timedelta('30min'))]
    elif phase=='After': view=ais[ais.timestamp>incident_time]
    else: view=ais
    fig=go.Figure(); c=infra.iloc[0]
    fig.add_trace(go.Scattermap(lat=[c.lat_start,c.lat_end],lon=[c.lon_start,c.lon_end],mode='lines',line={'width':6},name='Critical infrastructure'))
    for name,g in view.groupby('vessel_name'):
        width=4 if name==vessel else 2
        fig.add_trace(go.Scattermap(lat=g.latitude,lon=g.longitude,mode='lines+markers',line={'width':width},marker={'size':7 if name==vessel else 4},name=name,text=[f'{name}<br>{t}<br>{sp:.1f} kn<br>{d:.2f} km from incident' for t,sp,d in zip(g.timestamp,g.speed_kn,g.distance_to_incident_km)]))
    fig.add_trace(go.Scattermap(lat=[inc.latitude],lon=[inc.longitude],mode='markers',marker={'size':18},name='Incident'))
    fig.update_layout(map={'style':'carto-darkmatter','center':{'lat':59.84,'lon':24.9},'zoom':8},height=620,margin={'l':0,'r':0,'t':0,'b':0},legend={'orientation':'h','y':.01,'x':.01},paper_bgcolor='#071018',font={'color':'#dce7ed'})
    st.plotly_chart(fig,use_container_width=True)

st.markdown('### INCIDENT TIMELINE')
track=ais[ais.vessel_name==vessel].sort_values('timestamp')
closest=track.loc[track.distance_to_incident_km.idxmin()]
t1,t2,t3=st.columns(3)
t1.markdown(f'''<div class="panel"><b>BEFORE</b><br><span class="small">Track monitored approaching infrastructure zone.</span></div>''',unsafe_allow_html=True)
t2.markdown(f'''<div class="panel"><b>CLOSEST OBSERVATION</b><br>{closest.timestamp.strftime('%Y-%m-%d %H:%M')} UTC<br><span class="small">{closest.distance_to_incident_km:.2f} km • {closest.speed_kn:.1f} kn</span></div>''',unsafe_allow_html=True)
t3.markdown(f'''<div class="panel"><b>AFTER</b><br><span class="small">Track continues; retain for contextual review.</span></div>''',unsafe_allow_html=True)

st.markdown('### SOURCE FUSION & VERIFICATION')
s1,s2,s3,s4=st.columns(4)
s1.markdown('<div class="panel"><b>AIS observations</b><br><span class="small">DEMO DATA • INGESTED</span></div>',unsafe_allow_html=True)
s2.markdown('<div class="panel"><b>Infrastructure layer</b><br><span class="small">DEMO DATA • INGESTED</span></div>',unsafe_allow_html=True)
s3.markdown('<div class="panel"><b>Official sources</b><br><span class="small">NOT CONNECTED</span></div>',unsafe_allow_html=True)
s4.markdown('<div class="panel"><b>Open-source reporting</b><br><span class="small">NOT CONNECTED</span></div>',unsafe_allow_html=True)

st.markdown('### INTELLIGENCE BRIEF')
brief=f'''INITIAL SITUATION REPORT — SYNTHETIC DEMONSTRATION\n\nIncident: {inc['incident']}\nTime: {inc['timestamp']} UTC\nAsset: {inc['infrastructure']}\n\nObserved: {len(summary)} synthetic vessel tracks were evaluated around the demonstration incident. {int(summary.review_flag.sum())} track(s) met the prototype review rule based on proximity combined with low speed or course change.\n\nAssessment: The indicator set supports further analyst review only. It does not establish cause, intent, responsibility or attribution.\n\nNext collection: verify infrastructure status, ingest official reporting, compare historical vessel behaviour, and corroborate with independent sources.'''
st.text_area('Generated initial brief',brief,height=220)

st.markdown('### VESSEL OBSERVATIONS')
st.dataframe(summary[['vessel_name','closest_approach_km','min_speed_kn','max_speed_kn','course_change_deg','status']],use_container_width=True,hide_index=True)
st.caption('Prototype v0.2 • Synthetic demonstration dataset • Designed to demonstrate Detect → Verify → Contextualise → Assess → Decide.')
