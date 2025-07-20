+++
title = "IP Address Management in Cloud Infrastructure with ipam"
date = 2025-07-20
description = "Introducing a simple and efficient tool for managing IPs in Kubernetes and Bare-metal environments"
tags = ["DevOps", "Networking", "IPAM", "Kubernetes"]
author = "Hosein Montazer"
+++

In infrastructure projects — especially within **Kubernetes**, **on-prem networks**, or **bare-metal environments** — proper IP address management is essential. That’s why I developed [`ipam`](https://github.com/hoseinmontazer/ipam), a lightweight and reliable tool for managing IP allocation in modern environments.

## What is ipam?

`ipam` (short for **IP Address Management**) is a minimalistic tool for managing IP ranges and allocating free addresses. Unlike full-featured network systems, this tool focuses on **simplicity**, **clarity**, and **automation-friendliness**, making it a great fit for DevOps engineers and SREs who automate infrastructure at scale.

## Key Features

- Define IP pools using CIDR notation (e.g. `192.168.100.0/24`)
- Allocate the first available IP in a given pool
- Mark IPs as *reserved* or *used*
- Simple CLI interface — easily scriptable in CI/CD or Ansible workflows
- JSON-based storage — no need for an external database

## Use Cases

- IP allocation during deployment of services or VMs
- Reserving static IPs for specific hosts in bare-metal environments
- Checking whether a specific IP is free or in use
- Integrating with automation tools like **Ansible**, **Terraform**, or simple **Bash scripts**

## Getting Started

First, clone the project and build the binary:

```bash
git clone https://github.com/hoseinmontazer/ipam
cd ipam
go build -o ipam .
```


In many real-world projects, there’s no need to spin up complex systems like Infoblox or NetBox. Sometimes you just need a small tool that can help you allocate and track IPs — fast, lightweight, and dependency-free.

This project is open source, and contributions are welcome!
If you have a feature request or found a bug, feel free to open an issue or submit a pull request.

📎 Project link:  [github.com/hoseinmontazer/ipam](github.com/hoseinmontazer/ipam)


