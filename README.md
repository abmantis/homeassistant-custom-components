# homeassistant-custom-components
My custom components for Home Assistant

## Components:

### edp_redy:
Copy the following files: 
- edp_redy.py
- sensor/edp_redy.py
- switch/edp_redy.py

Add the following configuration:

```
edp_redy:
  username: 'xxxxx'
  password: 'xxxxx'
```
---
### edp_redy_local: 
**Prefer using the edp_redy component above, since edp_redy_local only provides sensors**

Copy the sensor/edp_redy_local.py and add the following configuration:

```
sensor:
  - platform: edp_redy_local
    host: 192.168.1.2
    update_interval: 10
```
