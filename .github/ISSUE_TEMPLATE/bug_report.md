---
name: Bug report
about: Something isn't working
title: ''
labels: bug
assignees: ''
---

**Server model / iLO generation**
e.g. ProLiant MicroServer Gen11, iLO 6 v1.74

**What happened**
A clear description of the problem.

**Relevant logs**
Settings -> System -> Logs, filtered for `ha-silo`.

**Redfish output (if a sensor is wrong/missing)**
Output of the relevant endpoint, e.g.
`curl -k -u USER:PASS https://ILO_IP/redfish/v1/Systems/1`
