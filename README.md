Informa
==========

A python project for running jobs on schedule. Built on the magic of
[rocketry](https://github.com/Miksus/rocketry).

Requires MQTT to track state.


Bootstrap
----------

An MQTT message needs to be published to topic "informa", which tracks the currently active plugins.
Since this application overloads the use of MQTT retained messages as a kind of persistent storage,
this step cannot be automated!

```
mosquitto_pub -h localhost -m '[]' -t informa/plugins -r
```
