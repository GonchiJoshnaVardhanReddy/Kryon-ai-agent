# Kryon

> An interactive concept demo for a hypothesis-driven, multi-agent security operations workspace.

**Kryon is currently a front-end prototype.** It demonstrates the operator experience and orchestration model; it does not connect to LLMs, scan targets, run security tools, or create real findings.

## What is here

Kryon is a single-page, dependency-free interface for exploring a safer model of AI-assisted security research. The prototype lets you switch between a standard chat view and a mission-control view, step through an eight-agent workflow, inspect each agent’s role, and review a simulated report.

The design centres on a simple principle: an autonomous security workflow should be evidence-led, explicitly scoped, and subject to human oversight. A finding should not be treated as confirmed just because a model or tool said so.

## Prototype capabilities

- Interactive chat and mission-control workspaces
- Simulated eight-agent orchestration run with status transitions and activity logs
- Agent detail panels covering reconnaissance, hypothesis generation, verification, defence, and reporting
- Approval prompt for a simulated high-risk action
- Example audit report and export interactions
- Responsive, zero-build static site with no runtime dependencies

## The proposed workflow

The interface models this security-research lifecycle:

```text
Passive recon → Active recon → Hypothesize → Test → Verify
      ↑                                              ↓
      └──────────── pending work / budget ──────────┘
                        ↓
              Defend → Report → Halt
```

The eight roles represented in the UI are:

| Role | Purpose |
| --- | --- |
| Passive Recon | Gather public, non-intrusive intelligence. |
| Active Recon | Map approved live attack surfaces. |
| Hypothesis Gen | Turn observed signals into concrete, testable claims. |
| Exploit Research | Execute approved test plans and capture evidence. |
| Post-Exploit | Model potential impact paths after confirmation. |
| Verification | Independently reproduce or reject proposed findings. |
| Blue Teaming | Pair confirmed findings with detection and response guidance. |
| Report Gen | Produce a clear, evidence-backed assessment report. |

## Run locally

No package installation or build step is required.

1. Clone the repository.
2. Open `index.html` in a modern browser.

For a local server instead:

```bash
python3 -m http.server 8080
```

Then visit `http://localhost:8080`.

## Project structure

```text
index.html  # Page structure and UI content
index.css   # Visual system, layout, and animations
index.js    # Demo interactions and simulated orchestration state
```

## Important boundaries

This repository is a visual prototype, not a security-testing tool. It does not enforce authorization, scope, rate limits, permissions, audit logging, sandboxing, or verification requirements. Do not infer production security capabilities from the simulated UI.

Any real implementation should require explicit written authorization, enforce target scope in code, keep an immutable audit trail, isolate tools, and require independent verification before reporting a vulnerability.

## Roadmap

The next meaningful implementation work would be to replace the simulated run with a scoped, auditable orchestration backend; define typed evidence and hypothesis schemas; and add real approval, budget, and verification controls before connecting any security tooling.

## License

No license file has been added yet. Until one is present, the repository is not offered under an open-source license.
