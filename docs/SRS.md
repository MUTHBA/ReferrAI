ReferrAI
Software Requirements Specification (SRS)
Version 2.1 — Simplified & Realistic Scope
Companion to BRD v2.1

1. Introduction
1.1 Purpose
This document specifies the functional and non-functional requirements for ReferrAI, a standalone referral and commission platform with seven integrated AI/ML features.
1.2 Scope
The system provides:
Referral Management
Commission Management
Partner Management
Wallet & Payout Tracking
Unified Admin Dashboard
Seven integrated AI capabilities
The following are outside the scope of the project:
Campaign Management
Marketing Asset Management
Configurable Workflow Engines

2. System Overview
ReferrAI is a single-deployment web application consisting of a React frontend, FastAPI backend, and PostgreSQL database.
AI features are implemented as Python services called directly by the backend. Trained machine learning models are loaded from saved model files.
Layer	Responsibility
Frontend (React)	Admin dashboard, Partner dashboard, Settings UI
Backend (FastAPI)	Authentication, Business Logic, Commission Calculation, AI Service Integration
AI Module (Python)	Synthetic Data Generation, Quality Prediction, Fraud Detection, Churn Prediction, Partner Ranking, Partner Discovery, Explainable AI
Database (PostgreSQL)	Stores all platform, referral, commission, partner, and AI-related data

3. Technology Stack
Layer	Technology
Frontend	React.js
Backend/API	FastAPI (Python)
Database	PostgreSQL
ORM	SQLAlchemy
Database Migration	Alembic
Authentication	JWT with Role-Based Access Control
Machine Learning	scikit-learn
Fraud Detection	Isolation Forest or Statistical (Z-score)
Embeddings	sentence-transformers
Explainability	Feature Importance / SHAP
Deployment	Docker

4. User Roles
Role	Permissions
Admin	Manage settings, partners, partner tiers, payouts, withdrawals, AI alerts, dashboards
Partner / Affiliate	Generate referral links and codes, view commissions, quality score, wallet, request withdrawals

5. Functional Requirements — Platform Core
5.1 Authentication Module
FR-AUTH-001 — System shall support user registration.
FR-AUTH-002 — System shall support login using email and password (JWT authentication).
FR-AUTH-003 — System shall support password reset via email.
FR-AUTH-004 — System shall enforce role-based access control for all API endpoints.

5.2 Referral Management Module
FR-REF-001 — Generate a unique referral code for every partner.
FR-REF-002 — Generate a unique referral link for every partner.
FR-REF-003 — Generate a QR code representing the referral link.
FR-REF-004 — Record every referral click including timestamp, referral source, and device/user-agent.
FR-REF-005 — Record every successful referral conversion linked to its originating click.
FR-REF-006 — Support configurable attribution using either First-Click or Last-Click models.

5.3 Commission Management Module
FR-COM-001 — Support percentage-based commissions.
FR-COM-002 — Support fixed-value commissions.
FR-COM-003 — Support tier-based commissions.
FR-COM-004 — Commission rules shall be configurable through the administrator settings page.
FR-COM-005 — Commission shall be calculated automatically whenever a referral conversion occurs.

5.4 Partner Management Module
FR-PRT-001 — Maintain partner profiles including name, category, contact information, status, and tier.
FR-PRT-002 — Support administrator-defined partner tiers.
FR-PRT-003 — Automatically upgrade partner tiers when administrator-defined thresholds are reached.
FR-PRT-004 — Track partner performance using referral volume, conversion rate, and revenue contribution.
FR-PRT-005 — Display each partner's AI-generated quality score, churn risk, and overall ranking.

5.5 Wallet & Payout Module
FR-WAL-001 — Maintain an individual wallet balance for every partner.
FR-WAL-002 — Support withdrawal requests.
FR-WAL-003 — Maintain complete payout and transaction history.
FR-WAL-004 — Automatically approve withdrawals below the administrator-defined threshold.
FR-WAL-005 — Require administrator approval for withdrawals from partners with active fraud flags regardless of withdrawal amount.

5.6 Dashboard & Reporting Module
FR-RPT-001 — Provide an administrator dashboard displaying referral volume, conversions, commissions, payouts, fraud alerts, and churn alerts.
FR-RPT-002 — Provide a partner dashboard displaying referrals, commissions, wallet balance, and referral quality score.
FR-RPT-003 — Allow dashboard data to be exported as CSV.

6. Functional Requirements — AI Features
The platform integrates seven AI capabilities as core system functionality.
6.1 Synthetic Data Generator (FR-AI-DATA)
Problem
No historical referral, fraud, or churn data exists when the platform is first deployed.
Approach
Generate configurable synthetic datasets containing:
Partner profiles
Referral events
Fraud patterns
Partner activity histories
Ground-truth fraud labels
Ground-truth churn labels
Synthetic records are stored using the same database tables as production data while being marked as synthetic.
Functional Requirements
FR-AI-DATA-001 — Generate configurable synthetic partners.
FR-AI-DATA-002 — Generate configurable referral click and conversion events.
FR-AI-DATA-003 — Generate configurable fraud patterns with known labels.
FR-AI-DATA-004 — Generate partner activity histories including churn labels.
FR-AI-DATA-005 — Mark all generated records as synthetic and exclude them from production reports by default.
Evaluation
Success is measured by the ability of downstream AI models to train and achieve their required evaluation metrics.

6.2 Referral Quality Prediction (FR-AI-QUAL)
Problem
Not every referral has the same probability of converting.
Approach
Binary classification using:
Logistic Regression
Gradient Boosting (optional enhancement)
Features include:
Referral source
Time-to-click
Historical conversion rate
Partner tier
Geographic match
Time of day
Functional Requirements
FR-AI-QUAL-001 — Generate a Referral Quality Score (0–100) for every referral.
FR-AI-QUAL-002 — Store both the score and contributing features.
FR-AI-QUAL-003 — Display the score on referral records and partner profiles.
Evaluation
Evaluate using:
ROC-AUC
Precision
Recall
Target performance:
ROC-AUC ≥ 0.75
Human decisions remain unaffected; the score is advisory only.

6.3 Fraud Detection (FR-AI-FRD)
Problem
Identify fraudulent referral activity before payouts occur.
Approach
Fraud detection combines:
Rule-based detection
Statistical anomaly detection
Rules include:
Referral velocity
Device/IP reuse
Self-referrals
Anomaly detection uses Isolation Forest or Z-score methods.
Functional Requirements
FR-AI-FRD-001 — Apply fraud detection rules to every referral.
FR-AI-FRD-002 — Compute anomaly-based fraud scores for partners.
FR-AI-FRD-003 — Combine rule-based and anomaly scores into a unified Fraud Risk Score.
FR-AI-FRD-004 — Add high-risk referrals and partners to the administrator review queue.
FR-AI-FRD-005 — Never automatically freeze accounts or deny payouts.
Evaluation
Evaluate using Precision and Recall on the synthetic fraud dataset while maintaining an acceptable false-positive rate.
Administrator review is always required before action is taken.
6.4 Partner Churn Prediction (FR-AI-CHURN)
Problem
Identify partners who are likely to become inactive so administrators can take preventive action.
Approach
Binary classification using features such as:
Referral volume trend
Conversion rate trend
Days since last activity
A partner is considered churned if no qualifying activity occurs within a configurable period.
Functional Requirements
FR-AI-CHURN-001 — Compute a Churn Risk Score (0–100) for every partner on a scheduled basis.
FR-AI-CHURN-002 — Display a ranked list of at-risk partners on the administrator dashboard.
FR-AI-CHURN-003 — Display churn risk on the partner profile and use it within Smart Partner Ranking.
Evaluation
Evaluate using PR-AUC on a held-out synthetic dataset while monitoring false-positive rates.
Predictions are advisory and do not trigger automated actions.

6.5 Smart Partner Ranking (FR-AI-RANK)
Problem
Provide administrators with an overall ranking of partner performance.
Approach
Compute a weighted composite score using:
Referral Quality Score
Churn Risk (inverted)
Referral Volume
Revenue Contribution
Weights remain configurable by administrators.
Functional Requirements
FR-AI-RANK-001 — Compute a composite ranking score for every partner.
FR-AI-RANK-002 — Display the contribution of every ranking factor.
FR-AI-RANK-003 — Allow administrators to configure ranking weights.
Evaluation
Validate ranking quality against administrator judgment using the synthetic dataset.

6.6 AI Partner Discovery (FR-AI-DISC)
Problem
Help administrators identify high-potential referral partners.
Approach
Candidate businesses are obtained from a curated dataset or sanctioned public API.
Each candidate is evaluated using:
Business category compatibility
Geographic compatibility
Text embedding similarity
Cosine similarity
Functional Requirements
FR-AI-DISC-001 — Accept candidate businesses with category, location, and descriptive information.
FR-AI-DISC-002 — Compute a Partner Potential Score (0–100).
FR-AI-DISC-003 — Present a ranked list of candidate partners together with contributing factors.
FR-AI-DISC-004 — Restrict data sources to curated datasets or sanctioned APIs.
Evaluation
Evaluate using Precision@K against manually labeled partner recommendations.

6.7 Explainable AI (FR-AI-XAI)
Problem
Every AI prediction should be understandable by users and administrators.
Approach
Rule-based fraud explanations display the triggering rule.
Machine learning predictions display the most influential features using Feature Importance or SHAP.
Functional Requirements
FR-AI-XAI-001 — Display the specific reason for every fraud flag.
FR-AI-XAI-002 — Display the top contributing factors for referral quality and churn predictions.
FR-AI-XAI-003 — Display only feature values actually used during prediction.
Evaluation
Verify that explanations correctly correspond to the features used by each prediction.

7. Admin Settings
The administrator shall be able to configure:
FR-SET-001 — Commission percentage or fixed amount for every tier.
FR-SET-002 — Tier qualification thresholds.
FR-SET-003 — Minimum withdrawal amount and automatic approval threshold.
FR-SET-004 — Referral attribution window.
FR-SET-005 — Fraud-score and churn-score alert thresholds.
FR-SET-006 — Record all settings changes with timestamps and audit logs.

8. Database Requirements
The platform uses PostgreSQL with SQLAlchemy and Alembic.
Entity	Purpose
Users	User authentication and roles
Partners	Partner information, tiers, status
ReferralLinks / ReferralCodes	Referral identifiers
ReferralClicks	Click tracking
ReferralConversions	Conversion tracking
Commissions	Commission records
Wallets	Partner wallet balances
Withdrawals	Withdrawal requests
Transactions	Wallet transaction history
Settings	Administrator-configurable settings
AIScores	Quality score, fraud score, churn score, explanations, model version, synthetic flag
FraudFlags	Fraud review records
DiscoveredPartners	AI Partner Discovery results
AuditLogs	Administrative activity and configuration history

9. Non-Functional Requirements
9.1 Performance
NFR-PER-001 — Standard API responses shall complete within 2 seconds.
NFR-PER-002 — Referral quality and fraud scoring shall not noticeably delay referral processing (target: under 1 second).

9.2 Security
NFR-SEC-001 — Passwords and authentication tokens shall never be stored in plaintext.
NFR-SEC-002 — Role-based access control shall be enforced for every endpoint.
NFR-SEC-003 — Administrative settings changes and fraud resolution actions shall be audit logged.
NFR-SEC-004 — HTTPS shall be used in deployed environments.

9.3 Reliability
NFR-REL-001 — If a machine learning model cannot be loaded, rule-based fraud detection shall continue operating so that fraud detection remains available.

10. Explicitly Not Built
The following features are outside the implementation scope:
Feature store
Model registry
Model drift monitoring
Fine-tuned LLMs
QLoRA
Campaign forecasting
AI outreach agents
Shapley-value attribution models
Markov-chain attribution models
Multi-tenant architecture
Horizontal scaling
Live payment gateway integration

11. Success Criteria
The project will be considered successful if:
All core platform functional requirements are fully implemented.
Referral → Conversion → Commission → Payout workflow functions correctly from end to end.
All seven AI features are implemented and satisfy their evaluation objectives.
Every fraud flag, referral quality score, and churn prediction includes an accurate explanation.
The complete system can be demonstrated live with referral processing, AI scoring, partner ranking, commission calculation, and dashboard updates operating successfully.
