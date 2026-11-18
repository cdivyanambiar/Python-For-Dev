# Fictional switch operations guide

## Offline switch
If a switch is offline, check its power and physical uplink first. Verify that the
management network is reachable and inspect the most recent device logs. If it
remains unreachable, escalate to the network operations team. These are generic
demo steps, not instructions for a specific product.

## High CPU
High CPU utilization can indicate sustained management traffic or a busy control
plane. Check whether utilization remains high over time, inspect recent changes,
and review process and interface statistics. Escalate persistent high CPU to the
network operations team. A single sample does not establish a root cause.

## Firmware
Before a firmware upgrade, verify model compatibility, review the release notes,
back up the configuration, and schedule an approved maintenance window. Follow
the vendor's official instructions for the actual device and software version.

## Temperature
For elevated switch temperature, check airflow, fans, and ambient temperature.
Consult the device-specific operating limits and escalate sustained overheating.
