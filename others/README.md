### edp_redy_local: 
**Prefer using the edp_redy component, since edp_redy_local only provides sensors**

Copy the sensor/edp_redy_local.py to your custom_components/sensor folder and add the following configuration:

```
sensor:
  - platform: edp_redy_local
    host: 192.168.1.2
    update_interval: 10
```
