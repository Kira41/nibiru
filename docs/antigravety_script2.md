# `script2.py`
**Recipient List Preparer & Extractor**

## Overview
This script exists to turn messy, raw lists of recipient emails (unstructured text) into clean, categorized outputs for campaigns.

## How it works
It parses raw pasted text, pulls valid email addresses, and groups them dynamically (for example, by recipient domain or TLD). It currently operates mostly on the frontend but maintains persistent storage metadata in `script2.db`. It prepares a final copyable list to act as the recipient payload for the sender module.

## Role
It acts as the recipient side list preparation tool—cleaning data before ingestion into an email blast.
