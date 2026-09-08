import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ThemeProvider, useTheme } from './components/theme-provider';
import BootupAnimation from './components/BootupAnimation';
import { Button } from './components/ui/button';
import { LogOut, User, Shield, Sun, Moon, Search, ShieldCheck } from 'lucide-react';
import { useAuth } from './context/AuthContext';

import LoginPage from './components/auth/LoginPage';
import RegisterPage from './components/auth/RegisterPage';
import ReAuthModal from './components/auth/ReAuthModal';

import DashboardOverview from './components/views/DashboardOverview';
import NetworkGraph from './components/views/NetworkGraph';
import AlertsFeed from './components/views/AlertsFeed';
import SearchInvestigation from './components/views/SearchInvestigation';
import DataCollectionStatus from './components/views/DataCollectionStatus';
import ReportingEvidence from './components/views/ReportingEvidence';
import AccessControl from './components/views/AccessControl';
import TrafficHotspots from './components/views/TrafficHotspots';
import SuspectProfiles from './components/views/SuspectProfiles';

import InvestigationList from './components/investigation/InvestigationList';
import InvestigationDetail from './components/investigation/InvestigationDetail';
import InvestigationCreate from './components/investigation/InvestigationCreate';
import AIAssistant from './components/ai/AIAssistant';

function InvestigationView() {
  const [selectedInvestigation, setSelectedInvestigation] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  return (
    <>
      {showCreateModal && (
        <InvestigationCreate
          onClose={() => setShowCreateModal(false)}
          onCreated={(newInv) => {
            setShowCreateModal(false);
            if (newInv?.id) setSelectedInvestigation(newInv.id);
          }}
        />
      )}
      {selectedInvestigation ? (
        <InvestigationDetail
          investigationId={selectedInvestigation}
          onBack={() => setSelectedInvestigation(null)}
        />
      ) : (
        <InvestigationList
          onSelectInvestigation={(inv) => setSelectedInvestigation(typeof inv === 'string' ? inv : (inv?.id || inv?.investigation_id))}
          onCreateClick={() => setShowCreateModal(true)}
        />
      )}
    </>
  );
}

function Dashboard() {
  const { t } = useTranslation();
  const { theme, setTheme } = useTheme();
  const { user, logout } = useAuth();
  const { i18n } = useTranslation();
  const [activeView, setActiveView] = useState('dashboard');

  const changeLang = (lng) => {
    i18n.changeLanguage(lng);
  };

  const renderActiveView = () => {
    switch (activeView) {
      case 'dashboard': return <DashboardOverview setActiveView={setActiveView} />;
      case 'investigations': return <InvestigationView />;
      case 'hotspots': return <TrafficHotspots />;
      case 'profiles': return <SuspectProfiles />;
      case 'data': return <DataCollectionStatus />;
      case 'alerts': return <AlertsFeed />;
      case 'network': return <NetworkGraph />;
      case 'search': return <SearchInvestigation />;
      case 'reports': return <ReportingEvidence />;
      case 'security': return <AccessControl />;
      default: return <DashboardOverview setActiveView={setActiveView} />;
    }
  };

  const navItems = [
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'investigations', label: 'Investigations' },
    { id: 'hotspots', label: 'Traffic Hotspots' },
    { id: 'profiles', label: 'Target Profiles' },
    { id: 'data', label: 'Data Collection Status' },
    { id: 'alerts', label: 'Alerts & Suspicious Activity' },
    { id: 'network', label: 'Network Visualization' },
    { id: 'search', label: 'Universal Search' },
    { id: 'reports', label: 'Reports & Evidence' },
    { id: 'security', label: 'Security & Access Control' },
  ];

  return (
    <div className="h-screen w-screen bg-background text-foreground flex flex-row font-sans relative z-0 overflow-hidden">
      {/* Background Effects */}
      <div className="absolute inset-0 pointer-events-none z-[-1] overflow-hidden">
        <div className="absolute top-[-20%] left-[-10%] w-[60%] h-[60%] bg-primary/20 rounded-full blur-[150px]" />
        <div className="absolute bottom-[-20%] right-[-10%] w-[60%] h-[60%] bg-primary/10 rounded-full blur-[150px]" />
      </div>
      <div className="absolute inset-0 bg-noise z-[-1]" />

      {/* LEFT COLUMN: SOLID NAVY BLUE SIDEBAR (Starts at y=0, covers full height) */}
      <aside className="w-[280px] bg-[#0B1E3D] text-white flex flex-col h-full flex-shrink-0 z-20 border-r border-[#1E4D8C]/40">
        {/* Logo & Title block inside top of sidebar (y=0) */}
        <div className="p-6 pb-5 flex items-center gap-3.5 border-b border-slate-700/50 flex-shrink-0">
          <div className="relative w-9 h-9 flex items-center justify-center bracket-border overflow-hidden flex-shrink-0 bg-slate-900/50">
            <img src="/top_right-Photoroom.png" alt="Emblem" className="w-full h-full object-cover" />
          </div>
          <div className="flex flex-col">
            <h1 className="text-lg font-bold tracking-[0.2em] text-white font-mono uppercase leading-none">DARKNIGHT</h1>
            <span className="text-[10px] text-slate-400 font-mono tracking-wider mt-1">Chandigarh Police</span>
          </div>
        </div>

        {/* Navigation Section */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          <div className="mb-4">
            <span className="text-xs font-mono tracking-widest text-slate-400 uppercase border-b border-slate-700/60 pb-2 block w-full">Navigation</span>
          </div>
          <div className="space-y-2.5">
            {navItems.map(item => (
              <div 
                key={item.id}
                onClick={() => setActiveView(item.id)}
                className={`flex items-center gap-3.5 px-3 py-2.5 rounded-lg group cursor-pointer transition-all ${
                  activeView === item.id 
                  ? 'bg-[#1E4D8C] text-white font-bold shadow-sm' 
                  : 'text-slate-300 hover:text-white hover:bg-slate-800/50'
                }`}
              >
                <div className={`w-2 h-2 rotate-45 flex-shrink-0 transition-all ${
                  activeView === item.id 
                  ? 'bg-[#3D7DC9] shadow-[0_0_8px_#3D7DC9]' 
                  : 'border border-slate-400 group-hover:border-white'
                }`} />
                <p className="font-mono text-xs tracking-[0.12em] uppercase">
                  {t(item.label) || item.label}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Chandigarh Police Branding Footer pinned to bottom of sidebar */}
        <div className="p-6 pt-4 border-t border-slate-700/50 flex flex-col items-center justify-center text-center mt-auto flex-shrink-0">
          <div className="w-8 h-8 mb-2 flex items-center justify-center text-slate-400">
            <ShieldCheck className="w-6 h-6 text-slate-400/80" />
          </div>
          <div className="flex items-center gap-2 w-full justify-center text-[10px] font-mono tracking-[0.2em] font-bold text-slate-400/80 uppercase">
            <span className="h-[1px] w-6 bg-slate-700/60"></span>
            <span>CHANDIGARH POLICE</span>
            <span className="h-[1px] w-6 bg-slate-700/60"></span>
          </div>
          <span className="text-[9px] font-mono tracking-[0.15em] text-slate-400/70 uppercase mt-1">
            FOR A SAFER TOMORROW
          </span>
        </div>
      </aside>

      {/* RIGHT COLUMN: MAIN CONTENT & UNIFIED TOP BAR (Starts at y=0) */}
      <div className="flex-1 flex flex-col h-full bg-background overflow-hidden">
        {/* Top bar shares main content background (starts at y=0, no top seam) */}
        <header className="h-16 bg-background flex items-center justify-end px-8 flex-shrink-0 z-10">
          <div className="flex items-center gap-4">
            {/* Authenticated Officer Badge */}
            {user && (
              <div className="flex items-center gap-3.5 px-3.5 py-1.5 bg-card border border-border/60 rounded-lg text-xs font-mono shadow-sm">
                <div className="flex flex-col text-right">
                  <span className="font-bold text-foreground">{user.full_name}</span>
                  <span className="text-[10px] text-primary uppercase font-bold">{user.role}</span>
                </div>
                <Button variant="ghost" size="icon" onClick={logout} title="Secure Logout" className="h-7 w-7 text-muted-foreground hover:text-destructive">
                  <LogOut className="w-4 h-4" />
                </Button>
              </div>
            )}

            {/* Language Switcher */}
            <div className="flex bg-muted/60 p-1 rounded-md border border-border/60">
              <Button variant={i18n.language === 'en' ? 'default' : 'ghost'} size="sm" onClick={() => changeLang('en')} className="h-7 text-xs px-2.5 font-mono">EN</Button>
              <Button variant={i18n.language === 'hi' ? 'default' : 'ghost'} size="sm" onClick={() => changeLang('hi')} className="h-7 text-xs px-2.5 font-mono">HI</Button>
              <Button variant={i18n.language === 'pa' ? 'default' : 'ghost'} size="sm" onClick={() => changeLang('pa')} className="h-7 text-xs px-2.5 font-mono">PA</Button>
            </div>

            {/* Mode Toggle */}
            <Button 
              variant="ghost" 
              size="sm"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              className="gap-2 font-mono text-xs border border-border/60 bg-card hover:bg-muted text-foreground font-bold px-3 h-9 rounded-lg"
            >
              {theme === "dark" ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-primary" />}
              {theme === "dark" ? "Light Mode" : "Dark Mode"}
            </Button>
          </div>
        </header>

        {/* Active View Container */}
        <section className="flex-1 bg-transparent px-8 pb-8 overflow-y-auto">
          {renderActiveView()}
        </section>
      </div>

      <ReAuthModal />
      <AIAssistant activeView={activeView} />
    </div>
  );
}

export default function App() {
  const [booting, setBooting] = useState(true);
  const [showRegister, setShowRegister] = useState(false);
  const { isAuthenticated, isLoading } = useAuth();

  if (booting) {
    return (
      <ThemeProvider defaultTheme="dark" storageKey="darknight-theme">
        <BootupAnimation onComplete={() => setBooting(false)} />
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider defaultTheme="light" storageKey="darknight-theme">
      {isLoading ? (
        <div className="h-screen w-full flex items-center justify-center bg-background text-primary font-mono text-sm">
          Loading Security Credentials...
        </div>
      ) : !isAuthenticated ? (
        showRegister ? (
          <RegisterPage onSwitchToLogin={() => setShowRegister(false)} />
        ) : (
          <LoginPage onSwitchToRegister={() => setShowRegister(true)} />
        )
      ) : (
        <Dashboard />
      )}
    </ThemeProvider>
  );
}
