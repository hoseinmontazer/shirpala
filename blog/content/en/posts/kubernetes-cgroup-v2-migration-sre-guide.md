+++
title = "Mandatory Shift to cgroup v2 in Kubernetes: Architecture, Limits, and SRE Migration Guide"
date = 2026-11-05T19:10:01Z
draft = false
description = "In-depth technical breakdown of Linux resource management changes with cgroup v2, OOM killer behavior, Memory QoS, and production migration guide for SREs."
tags = ["Kubernetes", "cgroup v2", "SRE", "Linux Kernel", "Resource Management"]
categories = ["Cloud & Infrastructure", "Linux & Operating Systems"]
author = "Hosein Montazer"
link = "https://kubernetes.io/blog/2026/10/06/kubernetes-cgroups-v2-shift/"
translationKey = "kubernetes-cgroup-v2-migration-sre-guide"
audio = ["/audio/posts/kubernetes-cgroup-v2-migration-sre-guide-en.mp3"]
audit_score = 100
+++

## Architectural Limitations of cgroup v1 and the Driver for Transition

In the Linux kernel, control groups (cgroups) serve as the fundamental mechanism for allocating hardware resources such as CPU, memory, and block I/O to operating system processes. In Kubernetes, this abstraction layer is directly responsible for container isolation, quality-of-service guarantees, and preventing resource contention between scheduled pods. Starting with Kubernetes v1.31, cgroup v1 support officially entered maintenance mode, following cgroup v2 being declared generally available and production-ready in v1.25. 

The core architectural flaw of cgroup v1 is its fragmented controller hierarchy: CPU, memory, blkio, and devices operated in completely independent trees. This made unified resource accounting virtually impossible, leading to synchronization deadlocks and severe inconsistencies between kernel controllers. Conversely, cgroup v2 provides a single unified hierarchy where every process belongs to exactly one cgroup path across all resource controllers, laying the groundwork for modern container sandboxing.

The transition timeline is now strictly enforced. From Kubernetes v1.35 onward, the kubelet configuration parameter `failCgroupV1` defaults to `true`. This means kubelet will refuse to start on nodes backed by cgroup v1 unless administrators explicitly override the flag. Complete removal of v1 code paths is tracked under KEP-5573. For clusters provisioned and upgraded via `kubeadm`, preflight system verification checks have been elevated: node initialization, joining, or upgrading on v1 will trigger immediate fatal errors rather than non-blocking warnings.

## Advanced cgroup v2 Primitives: Memory QoS and Group OOM

One of the most consequential improvements in cgroup v2 is group-level Out-of-Memory (OOM) handling. Under cgroup v1, memory starvation triggered the kernel OOM killer to terminate an arbitrary individual process within the cgroup, frequently leaving the container in an inconsistent zombie state with degraded sidecars or half-broken workers. In cgroup v2, kubelet configures `memory.oom.group` by default with `singleProcessOOMKill: false`, ensuring all processes belonging to the container are terminated atomically upon memory exhaustion.

Furthermore, Kubernetes v1.36 introduces Memory QoS (Alpha), which leverages cgroup v2 control files (`memory.high`, `memory.min`, and `memory.low`) to implement tiered resource guarantees:

- `memory.min`: Enforces hard memory protection for `Guaranteed` pods, preventing kernel page reclaim under global node pressure.
- `memory.low`: Provides soft protection for `Burstable` pods, prioritizing eviction of over-consuming best-effort workloads.
- `memory.high`: Applies gradual proportional throttling instead of immediate SIGKILL when containers breach transient burst thresholds.

```yaml
apiVersion: kubelet.config.k8s.io/v1beta1
kind: KubeletConfiguration
featureGates:
  MemoryQoS: true
memoryReservationPolicy: TieredReservation
memoryThrottlingFactor: 0.9
```

> **Kernel Requirement**: Memory QoS strictly requires Linux kernel 5.9+ to avoid reclaim livelocks previously observed with early `memory.high` implementations.

## Production Runbook and Best Practices for SREs

Platform and SRE teams executing cluster-wide migration should pay attention to several critical edge cases:

1. **Active Page Cache Accounting**: Under cgroup v1, `active_file` cache memory was often miscalculated, causing premature kubelet evictions during heavy sequential I/O workloads. While v2 unifies page cache accounting, SREs running storage-intensive pods (e.g., Kafka, PostgreSQL) should calibrate memory requests and limits to identical values based on continuous baseline telemetry.
2. **Rootless Containers and Delegation**: cgroup v2 provides first-class support for unprivileged delegation via systemd scopes (`systemd-run --user`), a prerequisite for production rootless container engines (Podman, Docker Rootless).
3. **eBPF Device Filtering**: Unlike v1's file-based pseudo-devices, cgroup v2 leverages eBPF programs for socket-level routing and device access control, unlocking superior packet throughput for CNIs like Cilium.
4. **Monitoring and Telemetry**: In cgroup v2, inspect the `memory.events` interface to export precise `oom`, `high`, and `max` counter spikes directly to your Prometheus node-exporter pipelines.

---
Source: [Kubernetes Official Blog — The Kubernetes Shift to cgroup v2](https://kubernetes.io/blog/2026/10/06/kubernetes-cgroups-v2-shift/)

