+++
title = "Projects"
date = 2025-07-20
description = "Open-source tools by Hosein Montazer – minimal, practical, and built for DevOps workflows"
tags = ["Projects", "Open Source", "DevOps", "Go"]
author = "Hosein Montazer"
+++

Here are a few open-source tools I've created and published on GitHub. These projects are focused on solving real-world infrastructure and productivity problems with simple, composable solutions.

---

## 📦 [`ipam`](https://github.com/hoseinmontazer/ipam)

A lightweight CLI tool for managing IP address ranges.  
Designed for DevOps engineers working in Kubernetes, bare-metal, or hybrid infrastructures.

**Key features:**

- Define and manage IP pools using CIDR (e.g. `192.168.10.0/24`)
- Get the first free IP address
- Mark IPs as `used`, `reserved`, or `free`
- JSON-based storage (no external DB)
- Scriptable via shell, Ansible, or CI/CD pipelines

**Use cases:**

- IP allocation in provisioning pipelines
- Bare-metal automation without heavy IPAM systems like NetBox
- Integrates cleanly into existing infrastructure scripts

---

## 🗒️ [`stickynotes`](https://github.com/hoseinmontazer/stickynotes)

A minimal sticky-notes web app written in Go with zero dependencies.  
Ideal for personal productivity or sharing quick notes across a local network.

**Features:**

- Single-binary web app (no database, no JS frameworks)
- Markdown support
- Edit notes directly from the browser
- Stores data in local files
- Extremely lightweight – perfect for local or self-hosted use

**Demo use cases:**

- Personal "note-to-self" board
- Internal dashboard for teams or homelab notes
- Embedded note widget in developer environments

---

## 🔗 Want More?

You can find all my open-source projects on GitHub:  
👉 [github.com/hoseinmontazer](https://github.com/hoseinmontazer)

I'm always looking to improve these tools — contributions, ideas, and bug reports are welcome!
