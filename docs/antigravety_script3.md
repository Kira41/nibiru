# `script3.py`
**Infrastructure Control Plane & Automation Engine**

## Overview
This application is the backend automation backbone for the physical and operational assets of the campaign system.

## How it works
It heavily integrates with remote external systems. For example, it connects to registrar APIs (like Namecheap via XML) to purchase and manipulate DNS records. It uses the `paramiko` library to SSH into remote servers to deploy changes, auto-generates PowerMTA configs (`/etc/pmta/config`), and oversees cryptographic DKIM/SPF domain verification. 

## Role
It acts as the canonical source of truth for the physical infrastructure the campaigns run on, keeping its state in `script3.db`.
