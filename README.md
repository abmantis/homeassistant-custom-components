# homeassistant-custom-components
My custom components for Home Assistant

## Components:

### edp_redy:
Copy the following files: 
- edp_redy.py
- switch/edp_redy.py
Add the following configuration:
```
edp_redy:
  username: 'xxxxx'
  password: 'xxxxx'
```

### edp_redy_local:
Copy the sensor/edp_redy_local.py and add the following configuration:

```
sensor:
  - platform: edp_redy_local
    host: 192.168.1.2
    update_interval: 10
```
