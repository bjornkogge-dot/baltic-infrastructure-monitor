# Baltic Infrastructure Monitor v1.3.1

Cable-layer reliability fix.

- Uses the official EMODnet Human Activities WFS endpoint.
- Resolves WFS layers by both machine name and human-readable title.
- Prioritises actual telecommunication cable routes over landing stations/schematic layers.
- Uses a WFS 1.1.0 GetFeature request with EPSG:4326 for the Baltic bbox.
- Supports MultiLineString and GeometryCollection.
- Makes cable routes visually thicker.
- Shows CABLE LAYER ONLINE/OFFLINE and connector diagnostics.
- Does **not** silently substitute fictional cable routes when the live source fails.

AIS remains sourced from Fintraffic Digitraffic. The local synthetic layer can still be enabled manually and is explicitly labelled.
