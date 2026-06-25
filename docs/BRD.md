ReferrAI
Business Requirements Document (BRD)
Version 2.1 — Simplified & Realistic Scope
Team: Vidyuth & Mukul
Duration: 12 Weeks

1. Executive Summary
ReferrAI is a standalone referral and commission management platform. Businesses use it to run referral programs, manage partners, automate commission and payout calculations, and detect fraud—with seven applied AI/ML features woven directly into the core workflow rather than offered as a side dashboard.
The platform is configurable rather than tied to one business: commission rules, tiers, and program settings are set through an admin settings screen, not hardcoded.
ReferrAI integrates seven AI capabilities directly into the referral workflow:
Synthetic Data Generation
Referral Quality Prediction
Fraud Detection
Partner Churn Prediction
Smart Partner Ranking
AI-assisted Partner Discovery
Explainable AI
These features are designed to provide meaningful automation, decision support, and transparency while remaining practical to implement within the project timeline.

2. Business Objectives
Primary Objectives
Build a standalone referral and commission platform with no business-specific hardcoding.
Let an admin configure commission rules, partner tiers, and program settings without touching code.
Automate commission calculation and payout tracking.
Score every referral for quality and fraud risk automatically.
Predict which partners are at risk of going inactive early enough to act.
Rank partners and surface high-potential new partners using AI rather than manual review.
Make every AI prediction explainable in plain language.
Secondary Objectives
Reduce manual commission tracking and spreadsheet work.
Give partners a transparent view of their own earnings and standing.
Demonstrate a complete, working end-to-end AI/ML pipeline.

3. Problem Statement
Businesses running referral or affiliate programs typically rely on spreadsheets and fragmented tools.
Common pain points include:
Manual commission calculation prone to error and dispute.
No visibility into which partners or referrals are actually driving conversions.
Fraudulent referrals (self-referrals, fake signups) that go undetected until money is already paid.
Rigid commission structures that require developer intervention.
No early warning when productive partners become inactive.
ReferrAI addresses these operational challenges using a configurable referral platform combined with integrated AI capabilities for detection, prediction, and decision support.

4. Scope
4.1 In Scope
Referral Management
Referral links
Referral codes
QR-code referrals
Click tracking
Conversion tracking
Configurable first-click / last-click attribution
Commission Management
Percentage-based commissions
Fixed-value commissions
Tier-based commissions
Automatic commission calculation after conversion
Partner Management
Partner onboarding
Partner profiles
Tier management
Automatic tier upgrades
Performance tracking
oReferral volume
oConversion rate
oRevenue contribution
Wallet & Payout
Wallet balance for every partner
Withdrawal requests
Payout history
Transaction history
Threshold-based payout approval
AI Capabilities
Synthetic Data Generator
Referral Quality Prediction
Fraud Detection
Partner Churn Prediction
Smart Partner Ranking
AI-assisted Partner Discovery
Explainable AI
Reporting & Analytics
Unified admin dashboard
Referral analytics
Commission analytics
Partner analytics
Fraud analytics
CSV export

4.2 Out of Scope
Campaign management
Marketing asset upload and management
Recurring commission models
Hybrid commission models
Configurable multi-step approval workflows
Multi-touch attribution
Multi-tenant / SaaS architecture
Inventory management
ERP functionality
CRM functionality
Accounting-system functionality
Live payment gateway integration

5. Target Users
The platform consists of two primary user roles.
Role	Responsibilities
Admin	Configure commission rules, tiers, and platform settings; manage partners; review payouts and withdrawals; review AI-flagged accounts; access analytics dashboard
Partner / Affiliate	Generate referral links and referral codes; view commissions, quality score, ranking, wallet balance; request withdrawals

6. Core Business Requirements
6.1 Referral Program Requirements
The platform shall support:
Referral links
Referral codes
QR codes
Click tracking
Conversion tracking
Configurable first-click or last-click attribution

6.2 Commission Requirements
The platform shall support:
Percentage commissions
Fixed commissions
Tier-based commissions
Commission rules shall be configurable by the admin and calculated automatically whenever a qualifying referral conversion occurs.

6.3 Partner Tier Requirements
The platform shall support custom tier structures with automatic tier upgrades based on administrator-defined performance thresholds.

6.4 Withdrawal Requirements
The platform shall:
Maintain wallet balances
Accept withdrawal requests
Apply a configurable auto-approval threshold
Requests exceeding the threshold, or submitted by partners with active fraud flags, require manual administrator approval.

7. Admin Settings
Administrators can configure:
Commission percentages or fixed amounts for each tier
Tier qualification thresholds
Minimum withdrawal amount
Auto-approval threshold
Referral eligibility window
All configuration changes are timestamped and recorded in audit logs.

8. AI Capabilities
8.1 Synthetic Data Generator
Purpose
A newly deployed referral platform has no historical referral, fraud, or churn data. The synthetic data generator creates realistic labeled datasets for training and evaluating the AI models.
Generated Data
Partners with hidden quality and behavior profiles
Referral events with realistic conversion probabilities
Fraudulent referral patterns
Partner activity histories including churn labels

8.2 Referral Quality Prediction / Scoring
Functionality
Predicts the likelihood that a referral converts using machine learning.
Possible models:
Logistic Regression
Gradient Boosting (optional enhancement)
Input features include:
Referral source
Partner history
Timing
Geographic match
Output:
Referral Quality Score (0–100)

8.3 Fraud Detection
Functionality
Detects suspicious referral activity using:
Rule-based detection
Statistical anomaly detection
Examples include:
Excessive referral velocity
Reused devices/IP addresses
Self-referrals
Outputs:
Fraud Risk Score
Review Flag
8.4 Partner Churn Prediction
Functionality
Predicts which partners are likely to become inactive using machine learning.
Input features include:
Referral volume trend
Days since last activity
Conversion rate trend
Output:
Churn Risk Score
Ranked list of at-risk partners

8.5 Smart Partner Ranking
Functionality
Ranks partners using a weighted combination of:
Referral Quality Score
Churn Risk (inverted)
Referral Volume
Revenue Contribution
The ranking provides administrators with an overall view of partner performance.

8.6 AI Partner Discovery
Functionality
Identifies potential referral partners from a curated dataset or sanctioned public API.
Each candidate is evaluated using:
Business category match
Geographic compatibility
Text embedding similarity using pretrained sentence-transformers
Cosine similarity scoring
Output:
Ranked candidate list
Partner Potential Score
Candidate data is obtained only from curated datasets or approved APIs.

8.7 Explainable AI
Functionality
Every AI prediction includes a human-readable explanation.
Examples include:
Fraud flags generated from triggered detection rules.
Referral quality explanations based on important prediction features.
Churn prediction explanations highlighting the most influential factors.
Feature importance (or SHAP, if implemented) is used to generate understandable explanations for machine learning predictions.

9. Success Criteria
The project will be considered successful if:
An administrator can configure referral programs, commission rules, and partner tiers without modifying code.
Commission calculation and payout tracking execute automatically and accurately.
Every referral receives a quality score.
Every fraud flag and churn prediction includes a clear explanation.
Fraud detection correctly identifies the majority of injected synthetic fraud cases while maintaining an acceptable false-positive rate.
The churn prediction model performs significantly better than random on held-out synthetic data.
AI Partner Discovery returns a meaningful ranked list of candidate partners.
The entire workflow operates successfully from referral creation through AI scoring, commission calculation, and dashboard updates.

10. Competitive Context
Existing referral platforms such as PartnerStack, Impact.com, and ReferralCandy provide referral tracking, commission management, and analytics.
ReferrAI differentiates itself by integrating AI directly into the referral workflow through:
Referral Quality Prediction
Fraud Detection
Partner Churn Prediction
Smart Partner Ranking
AI-assisted Partner Discovery
Explainable AI
These capabilities provide proactive insights instead of only descriptive reporting.
