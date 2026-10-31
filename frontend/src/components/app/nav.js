// -----------------------------------------------------------------------------
// Sidebar navigation for each role. `section` groups items under a heading;
// `end` marks routes that should only be active on an exact match.
// -----------------------------------------------------------------------------

import {
  ArrowLeftRight,
  Award,
  BrainCircuit,
  Compass,
  Coins,
  History,
  LayoutDashboard,
  Link2,
  ReceiptText,
  Settings,
  ShieldAlert,
  TrendingDown,
  Trophy,
  User,
  Users,
  Wallet,
  CirclePlus,
  Banknote,
} from 'lucide-react'

export const PARTNER_NAV = [
  {
    items: [
      { to: '/partner', label: 'Dashboard', icon: LayoutDashboard, end: true },
      { to: '/partner/links', label: 'Referral links', icon: Link2 },
      { to: '/partner/conversions', label: 'Conversions', icon: ArrowLeftRight },
      { to: '/partner/commissions', label: 'Commissions', icon: Coins },
      { to: '/partner/wallet', label: 'Wallet', icon: Wallet },
      { to: '/partner/profile', label: 'Profile', icon: User },
    ],
  },
]

export const ADMIN_NAV = [
  {
    section: 'Business',
    items: [
      { to: '/admin', label: 'Overview', icon: LayoutDashboard, end: true },
      { to: '/admin/partners', label: 'Partners', icon: Users },
      { to: '/admin/payouts', label: 'Payouts', icon: Banknote, badge: 'payouts' },
      { to: '/admin/commissions', label: 'Commissions', icon: ReceiptText },
      { to: '/admin/record-sale', label: 'Record a sale', icon: CirclePlus },
      { to: '/admin/tiers', label: 'Tiers', icon: Award },
      { to: '/admin/settings', label: 'Settings', icon: Settings },
    ],
  },
  {
    section: 'AI',
    items: [
      { to: '/admin/models', label: 'Models', icon: BrainCircuit },
      { to: '/admin/fraud', label: 'Fraud alerts', icon: ShieldAlert, badge: 'fraud' },
      { to: '/admin/churn', label: 'Churn risk', icon: TrendingDown },
      { to: '/admin/ranking', label: 'Ranking', icon: Trophy },
      { to: '/admin/discovery', label: 'Discovery', icon: Compass },
    ],
  },
  {
    section: 'Records',
    items: [{ to: '/admin/audit-log', label: 'Audit log', icon: History }],
  },
]
