# `script1.py`
**Sender Domain Screening**

## Overview
This script's goal is to rigorously vet and score candidate sender domains *before* they are introduced into the actual sending infrastructure.

## How it works
Operators paste lists of domains which the script tests via the Spamhaus API. It evaluates the domain's registration availability, risk score, and broader reputation. All of its queries and results are cached in a local SQLite file (`spamhaus_cache.db`), allowing the operator to selectively inspect and export "safe" domains to the infrastructure setup later.

## Role
It functions as a first-pass gatekeeper tool in the ecosystem.
