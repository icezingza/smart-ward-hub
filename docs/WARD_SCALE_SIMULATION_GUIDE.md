# Ward-Scale Simulation Guide

Run a synthetic ward of 40 beds against one local Hub contract:

```powershell
python ward_scale_simulation.py --beds 40 --ticks 8
```

The scenario injects one synthetic risk per selected bed:

| Bed | Scenario | Expected software result |
|---|---|---|
| `SIM-W01-B02` | suspected fall | `FALL` prototype signal after impact plus stable follow-up samples |
| `SIM-W01-B05` | low SpO2/high heart rate | `VITAL_ANOMALY` prototype signal |
| `SIM-W01-B08` | device stops reporting | `DEVICE_DISCONNECTED_STALE` and manual check required |
| `SIM-W01-B12` | synthetic perimeter loss | `DEVICE_PERIMETER_WARNING` and manual check required |
| `SIM-W01-B20` | requested low blood pressure | `BLOOD_PRESSURE_SENSOR_UNSUPPORTED`; manual BP measurement required |

`TelemetryPacket v1` has no blood-pressure, location, RSSI, or geofence field. The simulator therefore never pretends that these risks were sensed by the current Hub. Adding such a capability requires a versioned device contract, unit/range validation, device trust impact assessment, clinical review, and hardware bench evidence.

All records are synthetic and non-clinical. A successful run proves only local software behavior; it does not prove capacity on the target host, sensor accuracy, BLE coverage, clinical performance, or production readiness.
