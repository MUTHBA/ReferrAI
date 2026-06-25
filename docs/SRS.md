ReferrAI - Software Requirements Specification (SRS)

1. Introduction
1.1 Purpose

This document defines the functional and non-functional requirements for ReferrAI, a standalone referral and commission management platform with integrated AI capabilities.

1.2 Scope

ReferrAI provides:

Referral Management
Commission Management
Partner Management
Wallet & Payout Management
Dashboard & Reporting
AI-powered Referral Quality Scoring
AI-powered Fraud Detection
AI-powered Partner Churn Prediction
Smart Partner Ranking
AI Partner Discovery
Explainable AI
Synthetic Data Generation

The platform is configurable through an administrative settings module and supports referral-based business programs without requiring code changes.

2. System Overview

ReferrAI is a web-based application consisting of:

Layer	Responsibility
Frontend (React)	Admin Dashboard, Partner Dashboard, Settings Interface
Backend (FastAPI)	Authentication, Business Logic, Commission Processing, AI Integration
AI Module (Python)	Data Generation, Quality Scoring, Fraud Detection, Churn Prediction, Ranking, Discovery, Explainability
Database (PostgreSQL)	Storage of users, referrals, commissions, payouts, AI results, and settings
3. Technology Stack
Layer	Technology
Frontend	React.js
Backend	FastAPI
Database	PostgreSQL
ORM	SQLAlchemy
Database Migration	Alembic
Authentication	JWT Authentication
Machine Learning	Scikit-learn
Anomaly Detection	Isolation Forest / Statistical Methods
Embeddings	Sentence Transformers
Explainability	SHAP / Feature Importance
Deployment	Docker
4. User Roles
4.1 Admin

Permissions:

Manage platform settings
Configure commission structures
Configure partner tiers
Manage partners
Review withdrawals
Review fraud alerts
View AI insights
View reports and analytics
4.2 Partner / Affiliate

Permissions:

Generate referral links
Generate referral codes
Generate QR codes
View referrals
View commissions
View wallet balance
View quality score
Request withdrawals
5. Functional Requirements – Platform Core
5.1 Authentication Module
FR-AUTH-001

System shall support user registration.

FR-AUTH-002

System shall support login using email and password.

FR-AUTH-003

System shall support password reset through email.

FR-AUTH-004

System shall enforce role-based access control.

5.2 Referral Management Module
FR-REF-001

System shall generate a unique referral code for each partner.

FR-REF-002

System shall generate a unique referral link for each partner.

FR-REF-003

System shall generate a QR code for each referral link.

FR-REF-004

System shall log referral clicks including:

Timestamp
Source
Device information
FR-REF-005

System shall log referral conversions linked to referral clicks.

FR-REF-006

System shall support configurable attribution models:

First-click attribution
Last-click attribution
5.3 Commission Management Module
FR-COM-001

System shall support percentage-based commissions.

FR-COM-002

System shall support fixed-value commissions.

FR-COM-003

System shall support tier-based commissions.

FR-COM-004

Commission rules shall be configurable through the admin settings module.

FR-COM-005

Commission calculations shall occur automatically when a referral conversion is recorded.

5.4 Partner Management Module
FR-PRT-001

System shall maintain partner profiles containing:

Name
Category
Contact Information
Status
Tier
FR-PRT-002

System shall support administrator-defined partner tiers.

FR-PRT-003

System shall automatically upgrade partner tiers when configured thresholds are met.

FR-PRT-004

System shall track:

Referral Volume
Conversion Rate
Revenue Contribution
FR-PRT-005

System shall display:

Quality Score
Fraud Risk Score
Churn Risk Score
Partner Rank
5.5 Wallet & Payout Module
FR-WAL-001

System shall maintain a wallet balance for each partner.

FR-WAL-002

System shall support withdrawal requests.

FR-WAL-003

System shall maintain payout history and transaction history.

FR-WAL-004

System shall automatically approve withdrawal requests below an administrator-configured threshold.

FR-WAL-005

Withdrawal requests exceeding the configured threshold shall require manual administrator approval.

FR-WAL-006

Withdrawal requests from partners with active fraud flags shall require manual administrator approval.

5.6 Dashboard & Reporting Module
FR-RPT-001

System shall provide an administrator dashboard displaying:

Referral Volume
Conversion Count
Commission Totals
Payout Status
Fraud Alerts
Churn Alerts
FR-RPT-002

System shall provide a partner dashboard displaying:

Referrals
Commissions
Wallet Balance
Quality Score
Rank
FR-RPT-003

System shall support CSV export of dashboard data.

6. Functional Requirements – AI Features
6.1 Synthetic Data Generation
FR-AI-DATA-001

System shall generate synthetic partner records.

FR-AI-DATA-002

System shall generate synthetic referral click records.

FR-AI-DATA-003

System shall generate synthetic referral conversion records.

FR-AI-DATA-004

System shall generate synthetic fraud-labelled records.

FR-AI-DATA-005

System shall generate synthetic churn-labelled partner histories.

FR-AI-DATA-006

All synthetic records shall be marked using an is_synthetic flag.

6.2 Referral Quality Prediction
FR-AI-QUAL-001

System shall generate a referral quality score between 0 and 100.

FR-AI-QUAL-002

Quality scores shall be stored with referral records.

FR-AI-QUAL-003

Quality scores shall be displayed in:

Referral Details
Partner Profile
Dashboard
FR-AI-QUAL-004

System shall store the primary contributing factors associated with each quality score.

6.3 Fraud Detection
FR-AI-FRD-001

System shall perform fraud detection on referral activity.

FR-AI-FRD-002

System shall evaluate:

Referral Velocity
Device Reuse
IP Reuse
Self-Referral Patterns
FR-AI-FRD-003

System shall generate a fraud risk score between 0 and 100.

FR-AI-FRD-004

System shall create fraud alerts when configured thresholds are exceeded.

FR-AI-FRD-005

Fraud alerts shall be added to an administrator review queue.

FR-AI-FRD-006

System shall not automatically suspend accounts based solely on fraud predictions.

6.4 Partner Churn Prediction
FR-AI-CHURN-001

System shall generate a churn risk score between 0 and 100 for each partner.

FR-AI-CHURN-002

System shall identify partners at risk of becoming inactive.

FR-AI-CHURN-003

System shall display an at-risk partner list on the administrator dashboard.

FR-AI-CHURN-004

Churn risk scores shall be displayed on partner profiles.

6.5 Smart Partner Ranking
FR-AI-RANK-001

System shall calculate a composite partner ranking score.

FR-AI-RANK-002

Ranking shall consider:

Referral Quality Score
Churn Risk Score
Referral Volume
Revenue Contribution
FR-AI-RANK-003

System shall display ranked partner lists.

FR-AI-RANK-004

Ranking factor weights shall be configurable by administrators.

6.6 AI Partner Discovery
FR-AI-DISC-001

System shall accept candidate business data from approved datasets or APIs.

FR-AI-DISC-002

System shall generate a Partner Potential Score between 0 and 100.

FR-AI-DISC-003

Partner Potential Scores shall consider:

Business Category Match
Geographic Compatibility
Embedding Similarity
FR-AI-DISC-004

System shall present ranked candidate partners.

FR-AI-DISC-005

System shall display score-contributing factors.

6.7 Explainable AI
FR-AI-XAI-001

Every fraud alert shall include an explanation.

FR-AI-XAI-002

Every referral quality score shall include an explanation.

FR-AI-XAI-003

Every churn risk score shall include an explanation.

FR-AI-XAI-004

Explanations shall be based only on actual model inputs and outputs.

FR-AI-XAI-005

Explanations shall be presented in plain language.

7. Administrative Settings
FR-SET-001

System shall allow administrators to configure commission percentages.

FR-SET-002

System shall allow administrators to configure fixed commission values.

FR-SET-003

System shall allow administrators to configure partner tier thresholds.

FR-SET-004

System shall allow administrators to configure withdrawal limits.

FR-SET-005

System shall allow administrators to configure payout approval thresholds.

FR-SET-006

System shall allow administrators to configure referral attribution windows.

FR-SET-007

System shall allow administrators to configure fraud alert thresholds.

FR-SET-008

System shall allow administrators to configure churn alert thresholds.

FR-SET-009

All configuration changes shall be logged and timestamped.

8. Database Requirements
Entity	Purpose
Users	Authentication and role management
Partners	Partner information and status
ReferralLinks	Referral links
ReferralCodes	Referral codes
ReferralClicks	Referral click tracking
ReferralConversions	Referral conversion tracking
Commissions	Commission records
Wallets	Wallet balances
Withdrawals	Withdrawal requests
Transactions	Transaction history
Settings	Platform configuration
AIScores	AI predictions and explanations
FraudFlags	Fraud alerts and review status
DiscoveredPartners	Partner discovery records
AuditLogs	System activity logs
9. Non-Functional Requirements
9.1 Performance
NFR-PER-001

Standard API responses shall complete within 2 seconds.

NFR-PER-002

Referral quality and fraud scoring operations shall complete within 1 second.

9.2 Security
NFR-SEC-001

Passwords shall be securely hashed.

NFR-SEC-002

Sensitive tokens shall be securely stored.

NFR-SEC-003

Role-based access control shall be enforced across all endpoints.

NFR-SEC-004

Administrative actions shall be audit logged.

NFR-SEC-005

HTTPS shall be used in deployed environments.

9.3 Reliability
NFR-REL-001

The system shall continue operating if an AI model becomes unavailable.

NFR-REL-002

Referral tracking and fraud rule checks shall remain functional even when predictive models fail.

10. Success Criteria
Referral creation, conversion tracking, commission calculation, and payout management operate end-to-end.
All seven AI capabilities are operational within the platform.
Fraud alerts include explanations.
Referral quality scores include explanations.
Churn predictions include explanations.
Partner ranking updates dynamically based on performance.
AI Partner Discovery generates ranked recommendations.
Administrators can configure business rules without modifying code.
The platform can be demonstrated live from referral creation through commission payout tracking.