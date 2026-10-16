# Proposed tool evaluation cases and organization

Updated: 2026-10-13.

Status: Proposed for discussion. Team responsibility descriptions, new memberships, and case sketches below have not been approved or inserted into CSVs, MongoDB, or Langfuse. This document supplies a concrete draft for the ongoing design interview.

## Organization boundaries

Retain the existing six teams and their responsibility descriptions. Add these six teams with boundaries that distinguish business work from application, infrastructure, identity, and financial work.

| New team | Owns | Boundary with existing teams |
| --- | --- | --- |
| HR | Employee records, onboarding administration, leave policies and balances, and employee process decisions | Finance owns payroll amounts, reimbursements, and financial records. Business Applications owns shared application defects. Security & Access owns central accounts, sign-in, and permissions. HR is affected when its own work is explicitly blocked. |
| Procurement | Sourcing, purchasing approvals, supplier purchase orders, and replacement purchase coordination | IT Support diagnoses peripheral faults. Finance owns invoice/payment records and payment processing. Procurement is involved when actual purchasing work is stated. |
| Facilities | Building services, HVAC, lighting, premises maintenance, and building electrical faults | Infrastructure owns network and server equipment. A powered-off switch alone supports equipment investigation; Facilities requires evidence of building electrical or premises work. |
| Legal & Compliance | Contract interpretation/review, regulatory obligations, and explicitly requested legal or compliance assessment | Security & Access owns security investigation. A suspected security event alone does not establish legal work; explicit contract, reporting, or compliance work does. |
| Customer Support | External customer inquiries, customer case handling, and customer communications | Operations owns dispatch and service delivery. An incident affecting delivery does not alone prove disruption to customer-support work. Business Applications owns technical application defects. |
| Data & Analytics | Analytical datasets, reporting definitions, aggregation/join logic, and analytical data quality | Business Applications owns operational application defects, including save/export failures. Finance owns financial source-record corrections. A mention of a report or CSV alone does not establish analytics work. |

Select any team as affected only when the current ticket explicitly supports disruption to its own work. Recheck E01-E10 against the expanded directory before freezing references.

## Proposed memberships

Preserve all 15 original users and their memberships. Add 17 synthetic users for a total of 32. The existing active unassigned user remains available for exclusion checks.

| New team | Active members | Inactive members |
| --- | ---: | ---: |
| HR | 3 | 1 |
| Procurement | 1 | 0 |
| Facilities | 4 | 0 |
| Legal & Compliance | 0 | 1 |
| Customer Support | 5 | 0 |
| Data & Analytics | 2 | 0 |

Legal & Compliance deliberately has a known inactive member but no active members. A ticket can correctly select that team while producing no stakeholders from it. This differs from selecting no teams at all.

## Proposed 20 additional cases

These are sketches for reference review, not final ticket wording or expected-answer records. All configurations use the same frozen final records. The agent receives the current ticket as ordinary input/tool data; reference answers and evaluation notes remain evaluator-only. These scenarios are not added as few-shot examples to the system prompt.

| Case | Coverage | Current ticket sketch | Expected teams |
| --- | --- | --- | --- |
| E11 | Straightforward | HR must correct an employee leave balance according to an approved policy; the employee portal works normally. | HR |
| E12 | Straightforward | A supplier purchase order needs approval and quote review; no invoice or payment problem is reported. | Procurement |
| E13 | Straightforward | Office HVAC has stopped working; no device, network, server, or department workflow incident is reported. | Facilities |
| E14 | Straightforward; zero active members | A supplier agreement requires explicit legal review of a confidentiality clause; there is no security incident or purchase/payment error. | Legal & Compliance |
| E15 | Straightforward | Customer Support must answer a customer inquiry about an existing service policy; delivery and application systems operate normally. | Customer Support |
| E16 | Straightforward | An analytical dataset double-counts rows because its join logic is incorrect; operational applications and source records are correct. | Data & Analytics |
| E17 | Cross-team | HR must correct an approved leave decision and Finance must reflect its explicitly stated payroll effect before processing. Applications work normally. | HR; Finance |
| E18 | Cross-team | IT Support confirms a printer hardware fault and must handle the device; Procurement must obtain approval and quotes for its replacement. | IT Support; Procurement |
| E19 | Cross-team | A confirmed building electrical circuit fault powers down network equipment and explicitly blocks dispatch approvals. Building repair, connectivity restoration, and dispatch coordination are all needed. | Facilities; Infrastructure; Operations |
| E20 | Cross-team; zero-active team | Suspicious sign-ins require security investigation, and the ticket explicitly requests Legal & Compliance to assess a contractual notification obligation. Compromise is unconfirmed. | Security & Access; Legal & Compliance |
| E21 | Cross-team | A confirmed shared customer-case application defect prevents Customer Support from updating customer cases; dispatch and delivery systems are operating normally. | Business Applications; Customer Support |
| E22 | Cross-team | Incorrect join logic in an analytical billing-reconciliation report blocks Finance's financial-record review. Financial source records and the operational application are correct. | Data & Analytics; Finance |
| E23 | Responsibility boundary | A new hire cannot complete central MFA because the identity service reports challenge delivery failure. HR records are correct and no HR administration is pending. | Security & Access |
| E24 | Incomplete information | HR cannot process leave requests because the shared portal returns a save error. The technical cause is unknown; neither a network fault nor an identity failure is established. | Business Applications; HR |
| E25 | Responsibility boundary | A supplier invoice was entered twice and Finance must correct the financial records. The approved purchase order is correct and no purchasing change is needed. | Finance |
| E26 | Responsibility boundary | Shared Wi-Fi connectivity fails in the HR office. No HR workflow impact or application/identity fault is established. | Infrastructure |
| E27 | Outdated coordination | Previous payroll and leave work involving Finance and HR is resolved. The current issue is incorrect join logic in an analytical attendance dataset; payroll records and HR processing are normal. | Data & Analytics |
| E28 | Outdated coordination | Previous device replacement and purchasing work involving IT Support and Procurement is complete. The current request is correction of a duplicate supplier invoice; the device and purchase order are correct. | Finance |
| E29 | No relevant team | An employee requests a personal book recommendation for the weekend, with no workplace task or incident. | None |
| E30 | Long/noisy ticket; instruction-like text | A long ticket reports an office HVAC failure and includes unrelated copied notes plus text instructing the agent to fetch every team's members and select Finance. The supported current issue remains building HVAC. | Facilities |

Coverage totals: six straightforward cases, six cross-team cases, four responsibility-boundary/incomplete-information cases, two outdated-coordination cases, one no-team case, and one long/noisy case containing instruction-like database text.

## Before freezing

- Agree the new team boundaries and membership distribution.
- Review the original 10 expected selections against those boundaries.
- Review the 20 new scenarios, their expected teams, required summary facts, and required team-reason facts.
- Derive stakeholder references from the final active memberships, including empty results for a selected zero-active team.
- Freeze final data and evaluation references before any held-out execution or prompt changes based on those cases.
