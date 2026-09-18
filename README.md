# Baltic Infrastructure Monitor v1.3

First multi-source data-fusion prototype.

## Connected
- Fintraffic Digitraffic live AIS
- Fintraffic Portnet availability/context
- Fintraffic sea-state estimation availability
- Fintraffic AtoN fault availability
- EMODnet Human Activities WFS discovery for cables and pipelines

## Staged
- BarentsWatch / Norwegian Coastal Administration AIS. This requires registration and an API client/token, so credentials must be stored in Streamlit Secrets rather than committed to GitHub.

## Architecture
OBSERVED → CORRELATED → CORROBORATED → ASSESSED

Source identity is preserved throughout the UI. Proximity or vessel movement alone is not treated as evidence of causation, intent, wrongdoing or attribution.

## Run
```bash
pip install -r requirements.txt
streamlit run app.py
```
