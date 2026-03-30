# `script5.py`
**Email Open Tracking & Analytics Generation**

## Overview
Script 5 is responsible for generating trackable metrics to evaluate campaign success.

## How it works
It establishes a robust system by generating unique persistent numbers/pixel URLs for every recipient email address involved in a campaign. These tracking images are zipped and served externally. When a tracking image is loaded by a user, that remote tracking server updates an `image_log.jsonl` log file. The script then correlates logs against the unique identifiers generated here in `tracker.db` to measure "opened" events and map them back to specific users.

## Role
Engagement analytics and post-delivery success tracking.
