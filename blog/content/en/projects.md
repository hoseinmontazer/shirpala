+++
title = "Projects"
date = 2025-07-20
description = "Open-source tools by Hosein Montazer"
tags = ["Projects", "Open Source", "Go", "DevOps"]
author = "Hosein Montazer"
+++


---

## 🔧 docker_registry_proxy

A lightweight Go-based proxy for Docker Registry (Docker Hub), designed to bypass access restrictions caused by censorship, sanctions, or network-level blocks — especially for individual developers and professionals in restricted regions :contentReference[oaicite:4]{index=4}.

**Features:**
- Transparent proxying for Docker Hub `/v2/` API  
- Automatic token-based authentication  
- CORS & logging middleware  
- Configurable via environment variables  
- Ideal for Docker clients, CI/CD pipelines, etc.

**Usage:**
```bash
go get github.com/hoseinmontazer/docker_registry_proxy
# or run via Docker