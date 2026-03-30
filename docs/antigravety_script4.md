# `script4.py` (and `script4.html`)
**The Mailer Frontend Prototype**

## Overview
Used to act as the specific front-end for defining senders, servers, jobs, and the message content itself.

## How it works
Historically, `script4` represents the UI/operations layer for running sending campaigns. It would handle the definitions for SMTP configuration, executing the mail deliveries, and tracking preflight validation checks. 

## Role
While still active in the backend for orchestrating SMTP job queues, much of its interface capabilities are currently being deprecated and folded directly into the centralized user shell provided by `nibiru.py`.
