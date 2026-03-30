# `nibiru.py`
**The Unified Application Shell & Orchestrator**

## Overview
`nibiru.py` is intended to unify the scattered, independent tools of the project into a single, cohesive operator interface. 

## How it works
It establishes an all-in-one Flask backend that serves a unified dashboard. At present, this file specifically owns the "mailer" and send-orchestration surface (replacing old, standalone HTML mailers like `script4.html`). It ties into internal databases and acts as the central command post for creating campaigns, monitoring sending logic, and defining multi-server distribution.

## Purpose
Its ultimate goal is to become the final application shell, absorbing the functionality of all other scripts into one robust platform.
