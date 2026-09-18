# Baltic Infrastructure Monitor v1.2

v1.2 adds a real open-data connector to Fintraffic Digitraffic's Finnish marine AIS API.

## Data modes
- **Fintraffic Digitraffic — LIVE:** current open AIS vessel positions and metadata.
- **Synthetic demo:** local fallback/demo dataset.

The infrastructure layer remains synthetic and is labelled as such.

## Run
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Important limitations
AIS is an observation source, not proof of identity, intent, causation or attribution. Coverage can be incomplete, delayed or erroneous. Corroborate operational conclusions with independent sources.

## Open-data sources for expansion
- Fintraffic Digitraffic marine traffic / AIS
- Norwegian Coastal Administration / BarentsWatch AIS
